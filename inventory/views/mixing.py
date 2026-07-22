"""Mixing jobs: index/create/preview/detail/finish/cancel/plan/start."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from ..forms import (
    MixingPlanForm,
)
from ..models import (
    Branch,
    MixingJob,
    Product,
    RecipeComponent,
    Stock,
)
from ..services import (
    cancel_mixing_job,
    finish_mixing_job,
    plan_mixing_job,
    record_completed_mixing_job,
    start_mixing_job,
)


@require_GET
def mixing_job_index(request):
    """Recent mixing jobs, branch-scoped for obsluha."""
    qs = (
        MixingJob.objects.select_related(
            "branch", "mixture", "created_by"
        ).order_by("-started_at", "-id")
    )
    if request.user.is_obsluha and request.user.branch_id:
        qs = qs.filter(branch_id=request.user.branch_id)
    jobs = list(qs[:100])
    return render(
        request,
        "inventory/mixing_job_index.html",
        {"jobs": jobs, "count": len(jobs)},
    )


@require_http_methods(["GET", "POST"])
def mixing_job_create(request):
    """Pick a mixture + target qty → one immediate DONE míchání (per 0060).

    GET shows the form + (after HTMX preview swap) the derived
    consumption per component vs. on-hand stock.
    POST consumes the recipe inputs and adds the blend in one atomic
    action via record_completed_mixing_job() and lands on the job detail.
    On error the form re-renders with every typed value preserved.
    """
    mixtures = list(
        Product.objects.filter(
            kind=Product.Kind.MIXTURE,
            is_active=True,
            recipe_components__isnull=False,
        )
        .distinct()
        .order_by("name_cs")
    )
    branches = list(Branch.objects.filter(is_active=True).order_by("code"))
    default_branch = (
        request.user.branch
        if request.user.branch_id
        else (branches[0] if branches else None)
    )
    # Pre-select the směs when arriving from a recipe page (?mixture=<pk>);
    # keep the selection on POST validation errors.
    selected_mixture_id = (
        request.POST.get("mixture")
        if request.method == "POST"
        else request.GET.get("mixture")
    ) or ""
    # On POST these carry the operator's typed values back into the form so
    # a shortage (or any error) doesn't wipe the entry (per 0060, 3b). On GET
    # they also honour a `?branch=&target_qty=` round-trip from the inventura
    # "Upravit stav surovin" jump so the selection is restored on return.
    selected_branch_id = (
        request.POST.get("branch")
        if request.method == "POST"
        else request.GET.get("branch", "")
        or (str(default_branch.pk) if default_branch else "")
    ) or ""
    target_qty_value = (
        request.POST.get("target_qty", "")
        if request.method == "POST"
        else request.GET.get("target_qty", "")
    )
    # Per 0089: a {str(pk): "<1dp dot str>"} map of mixtures with a default batch
    # set (> 0). Emitted as a json_script blob so the dropdown-change JS can
    # overwrite the total when the operator picks a recipe. Built off the already-
    # hydrated `mixtures` list — zero extra queries.
    def _batch_1dp(m):
        return str(m.default_batch_kg.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

    mixture_defaults = {
        str(m.pk): _batch_1dp(m) for m in mixtures if m.default_batch_kg > 0
    }
    # GET-only server prefill: a plain `?mixture=<pk>` link (from product-detail)
    # lands with the total already filled. Never on POST — that would clobber the
    # overdraw re-render echo the tests assert. Only when no explicit ?target_qty=
    # was passed (an explicit value always wins).
    if (
        request.method == "GET"
        and not target_qty_value
        and str(selected_mixture_id) in mixture_defaults
    ):
        target_qty_value = mixture_defaults[str(selected_mixture_id)]
    actual_produced_value = (
        request.POST.get("actual_produced_qty", "") if request.method == "POST" else ""
    )
    note_value = request.POST.get("note", "") if request.method == "POST" else ""

    error: str | None = None
    if request.method == "POST":
        try:
            branch_id = int(request.POST.get("branch", "") or 0)
            branch = Branch.objects.get(pk=branch_id)
        except (ValueError, Branch.DoesNotExist):
            error = "Vyberte pobočku."
            branch = None
        try:
            mixture_id = int(request.POST.get("mixture", "") or 0)
            mixture = Product.objects.get(pk=mixture_id, kind=Product.Kind.MIXTURE)
        except (ValueError, Product.DoesNotExist):
            error = error or "Vyberte směs."
            mixture = None
        try:
            target_qty = Decimal(request.POST.get("target_qty", ""))
        except (InvalidOperation, ValueError):
            error = error or "Cílové množství musí být číslo."
            target_qty = None
        note = request.POST.get("note", "").strip()

        if branch is not None and mixture is not None and target_qty is not None:
            if (
                request.user.is_obsluha
                and request.user.branch_id != branch.pk
            ):
                error = "Nemáte oprávnění pro tuto pobočku."
            else:
                # "Skutečně vyrobeno" is an optional override; blank → target.
                try:
                    actual_produced_qty = Decimal(
                        request.POST.get("actual_produced_qty", "")
                    )
                except (InvalidOperation, ValueError):
                    actual_produced_qty = target_qty
                try:
                    job = record_completed_mixing_job(
                        branch=branch,
                        mixture=mixture,
                        target_qty=target_qty,
                        actual_produced_qty=actual_produced_qty,
                        user=request.user,
                        note=note,
                    )
                    messages.success(
                        request,
                        f"Namícháno — {job.actual_produced_qty} kg {mixture.name_cs}.",
                    )
                    return redirect("inventory:mixing_job_detail", pk=job.pk)
                except ValidationError as exc:
                    error = "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)

    return render(
        request,
        "inventory/mixing_job_create.html",
        {
            "mixtures": mixtures,
            "branches": branches,
            "default_branch": default_branch,
            "is_branch_locked": bool(
                request.user.is_obsluha and request.user.branch_id
            ),
            "selected_mixture_id": str(selected_mixture_id),
            "selected_branch_id": str(selected_branch_id),
            "target_qty_value": target_qty_value,
            "mixture_defaults": mixture_defaults,
            "actual_produced_value": actual_produced_value,
            "note_value": note_value,
            "error": error,
        },
    )


@require_GET
def mixing_preview_partial(request):
    """HTMX: given branch + mixture + target_qty, return the derived
    consumption table + stock-availability flags."""
    try:
        branch_id = int(request.GET.get("branch", "") or 0)
        branch = Branch.objects.get(pk=branch_id)
    except (ValueError, Branch.DoesNotExist):
        return HttpResponse("")
    try:
        mixture_id = int(request.GET.get("mixture", "") or 0)
        mixture = Product.objects.get(pk=mixture_id, kind=Product.Kind.MIXTURE)
    except (ValueError, Product.DoesNotExist):
        return HttpResponse("")
    try:
        target_qty = Decimal(request.GET.get("target_qty", ""))
        if target_qty <= 0:
            return HttpResponse("")
    except (InvalidOperation, ValueError):
        return HttpResponse("")

    recipe = list(
        RecipeComponent.objects.filter(mixture_product=mixture)
        .select_related("component_product")
        .order_by("position", "id")
    )
    stock_by_product = {
        s.product_id: s.quantity
        for s in Stock.objects.filter(
            product__in=[rc.component_product_id for rc in recipe],
            branch=branch,
        )
    }
    rows = []
    any_overdraw = False
    for rc in recipe:
        derived = (target_qty * rc.ratio).quantize(Decimal("0.001"))
        # Untracked components (per 0088, e.g. „Voda“) are unlimited — never
        # over, never counted into the overdraw warning card; the template
        # renders „neomezeno" for their on-hand.
        untracked = not rc.component_product.is_stock_tracked
        on_hand = stock_by_product.get(rc.component_product_id, Decimal("0.000"))
        over = (derived > on_hand) and not untracked
        if over:
            any_overdraw = True
        rows.append(
            {
                "component": rc.component_product,
                "ratio": rc.ratio,
                "derived": derived,
                "on_hand": on_hand,
                "over": over,
                "untracked": untracked,
            }
        )
    # "Upravit stav surovin" jump: per-branch inventura pre-filtered to this
    # blend's components (?products=…), with a `next=` back to the míchání
    # form carrying the current selection (per 0060, 3c). Untracked components
    # are excluded — inventura never lists them.
    component_ids = ",".join(
        str(rc.component_product_id)
        for rc in recipe
        if rc.component_product.is_stock_tracked
    )
    michani_next = (
        reverse("inventory:mixing_job_create")
        + "?"
        + urlencode(
            {
                "branch": branch.pk,
                "mixture": mixture.pk,
                "target_qty": target_qty,
            }
        )
    )
    inventura_link = (
        reverse("inventory:inventura_edit", args=[branch.code])
        + "?"
        + urlencode({"products": component_ids, "next": michani_next})
    )
    return render(
        request,
        "inventory/_mixing_preview.html",
        {
            "rows": rows,
            "any_overdraw": any_overdraw,
            "target_qty": target_qty,
            "mixture": mixture,
            "inventura_link": inventura_link,
        },
    )


@require_GET
def mixing_job_detail(request, pk: int):
    job = get_object_or_404(
        MixingJob.objects.select_related(
            "branch", "mixture", "created_by", "consume_movement", "produce_movement"
        ),
        pk=pk,
    )
    if (
        request.user.is_obsluha
        and request.user.branch_id != job.branch_id
    ):
        return HttpResponse(
            "Nemáte oprávnění zobrazit tuto dávku.",
            content_type="text/plain; charset=utf-8",
            status=403,
        )
    lines = list(
        # id order = creation order = recipe position order at plan time (0092)
        job.lines.select_related("component_product").order_by("id")
    )
    return render(
        request,
        "inventory/mixing_job_detail.html",
        {"job": job, "lines": lines},
    )


@require_http_methods(["POST"])
def mixing_job_finish(request, pk: int):
    job = get_object_or_404(MixingJob, pk=pk)
    if (
        request.user.is_obsluha
        and request.user.branch_id != job.branch_id
    ):
        return HttpResponse(
            "Nemáte oprávnění upravit tuto dávku.",
            content_type="text/plain; charset=utf-8",
            status=403,
        )
    try:
        actual_produced_qty = Decimal(request.POST.get("actual_produced_qty", ""))
    except (InvalidOperation, ValueError):
        messages.error(request, "Skutečné vyrobené množství musí být číslo.")
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    line_actuals: dict[int, Decimal] = {}
    for jl in job.lines.all():
        raw = request.POST.get(f"line-{jl.pk}-actual_qty")
        if raw is None or raw == "":
            continue
        try:
            line_actuals[jl.pk] = Decimal(raw)
        except (InvalidOperation, ValueError):
            messages.error(
                request, f"Spotřeba {jl.component_product} musí být číslo."
            )
            return redirect("inventory:mixing_job_detail", pk=job.pk)
    try:
        finish_mixing_job(
            mixing_job=job,
            actual_produced_qty=actual_produced_qty,
            line_actuals=line_actuals,
            user=request.user,
        )
    except ValidationError as exc:
        messages.error(
            request,
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
        )
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    messages.success(request, "Dávka dokončena.")
    return redirect("inventory:mixing_job_detail", pk=job.pk)


@require_http_methods(["POST"])
def mixing_job_cancel(request, pk: int):
    job = get_object_or_404(MixingJob, pk=pk)
    if (
        request.user.is_obsluha
        and request.user.branch_id != job.branch_id
    ):
        return HttpResponse(
            "Nemáte oprávnění upravit tuto dávku.",
            content_type="text/plain; charset=utf-8",
            status=403,
        )
    reason = (request.POST.get("reason") or "").strip()
    if not reason:
        messages.error(request, "Důvod zrušení je povinný.")
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    try:
        cancel_mixing_job(mixing_job=job, reason=reason, user=request.user)
    except ValidationError as exc:
        messages.error(
            request,
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
        )
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    messages.success(request, "Dávka zrušena.")
    return redirect("inventory:mixing_job_detail", pk=job.pk)


# ---------------------------------------------------------------------------
# Screen 14 — Nastavení (operator-facing Settings UI)
# ---------------------------------------------------------------------------



def mixing_plan_create(request):
    """Create a PLANNED MixingJob — no stock consumed. Operator clicks
    "Spustit teď" on the detail page to transition to RUNNING."""
    if request.method == "POST":
        form = MixingPlanForm(request.POST, user=request.user)
        if form.is_valid():
            branch = form.cleaned_data["branch"]
            if (
                request.user.is_obsluha
                and request.user.branch_id != branch.pk
            ):
                form.add_error(
                    "branch", "Nemáte oprávnění pro tuto pobočku."
                )
            else:
                try:
                    job = plan_mixing_job(
                        branch=branch,
                        mixture=form.cleaned_data["mixture"],
                        target_qty=form.cleaned_data["target_qty"],
                        user=request.user,
                        planned_for=form.cleaned_data.get("planned_for"),
                        note=form.cleaned_data.get("note", ""),
                    )
                except ValidationError as exc:
                    form.add_error(
                        None,
                        "; ".join(exc.messages)
                        if hasattr(exc, "messages")
                        else str(exc),
                    )
                else:
                    messages.success(
                        request,
                        f"Plánovaná dávka {job.mixture.name_cs} "
                        f"{job.target_qty} kg vytvořena.",
                    )
                    return redirect("inventory:mixing_job_detail", pk=job.pk)
    else:
        form = MixingPlanForm(user=request.user)
    return render(
        request,
        "inventory/mixing_plan_form.html",
        {"form": form},
    )


@require_POST
def mixing_job_start(request, pk: int):
    """Transition a PLANNED MixingJob to RUNNING (consumes stock)."""
    job = get_object_or_404(MixingJob, pk=pk)
    if (
        request.user.is_obsluha
        and request.user.branch_id != job.branch_id
    ):
        return HttpResponse(
            "Nemáte oprávnění upravit tuto dávku.",
            content_type="text/plain; charset=utf-8",
            status=403,
        )
    try:
        start_mixing_job(job=job, user=request.user)
    except ValidationError as exc:
        messages.error(
            request,
            "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc),
        )
        return redirect("inventory:mixing_job_detail", pk=job.pk)
    messages.success(request, "Dávka spuštěna — stav skladu byl odečten.")
    return redirect("inventory:mixing_job_detail", pk=job.pk)


# ---------------------------------------------------------------------------
# Podpora (in-app docs + feedback log, per decision 0046)
# ---------------------------------------------------------------------------


