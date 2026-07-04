"""Reusable class-based CRUD for archivable číselník masters (decision 0068).

Collapses the near-identical Supplier/Customer index/create/edit/archive/
reactivate views onto five configurable ``View`` subclasses. Each concrete
endpoint is produced with ``.as_view(model=…, template=…, …)`` in
``ciselniky.py`` — no per-model subclass needed, except where a guard differs
(``CustomerArchiveView`` adds the default-recipient block).

Branch CRUD is intentionally NOT built on these: its ``code`` URL kwarg,
vlastník gating, and stock/active-user archive guards make it a poor fit — it
stays function-based (right-sized-for-small-business).

Message templates use ``{obj}`` — e.g. ``"Dodavatel {obj.name} přidán."`` —
formatted with the affected instance.
"""

from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View


class ArchivableIndexView(View):
    """GET list with active/archived/all filter (``?status=``)."""

    http_method_names = ["get"]
    model = None
    template = ""
    context_list_name = ""  # e.g. "suppliers"
    exclude_internal = True

    def get(self, request):
        qs = self.model.objects.order_by("name")
        if self.exclude_internal:
            qs = qs.exclude(is_internal=True)
        status = request.GET.get("status") or "active"
        if status == "active":
            qs = qs.filter(is_active=True)
        elif status == "archived":
            qs = qs.filter(is_active=False)
        return render(
            request,
            self.template,
            {self.context_list_name: list(qs), "filter_status": status},
        )


class ArchivableCreateView(View):
    model = None
    form_class = None
    template = ""
    index_url = ""       # url name to redirect to on success
    created_msg = ""     # e.g. "Dodavatel {obj.name} přidán."

    def get(self, request):
        form = self.form_class(initial={"is_active": True})
        return render(request, self.template, {"form": form, "mode": "create"})

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, self.created_msg.format(obj=obj))
            return redirect(self.index_url)
        return render(request, self.template, {"form": form, "mode": "create"})


class ArchivableEditView(View):
    model = None
    form_class = None
    template = ""
    index_url = ""
    internal_block_msg = None  # if set, internal rows can't be edited here

    def _blocked(self, obj) -> str | None:
        if self.internal_block_msg and getattr(obj, "is_internal", False):
            return self.internal_block_msg
        return None

    def get(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        err = self._blocked(obj)
        if err:
            messages.error(request, err)
            return redirect(self.index_url)
        form = self.form_class(instance=obj)
        return render(
            request, self.template, {"form": form, "mode": "edit", "target": obj}
        )

    def post(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        err = self._blocked(obj)
        if err:
            messages.error(request, err)
            return redirect(self.index_url)
        form = self.form_class(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Změny uloženy.")
            return redirect(self.index_url)
        return render(
            request, self.template, {"form": form, "mode": "edit", "target": obj}
        )


class ArchivableArchiveView(View):
    http_method_names = ["post"]
    model = None
    index_url = ""
    archived_msg = ""          # "Dodavatel {obj.name} archivován."
    internal_block_msg = None  # "Interní dodavatele nelze archivovat."

    def blocked(self, obj) -> str | None:
        if self.internal_block_msg and getattr(obj, "is_internal", False):
            return self.internal_block_msg
        return None

    def post(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        err = self.blocked(obj)
        if err:
            messages.error(request, err)
            return redirect(self.index_url)
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        messages.success(request, self.archived_msg.format(obj=obj))
        return redirect(self.index_url)


class ArchivableReactivateView(View):
    http_method_names = ["post"]
    model = None
    index_url = ""
    reactivated_msg = ""

    def post(self, request, pk):
        obj = get_object_or_404(self.model, pk=pk)
        obj.is_active = True
        obj.save(update_fields=["is_active"])
        messages.success(request, self.reactivated_msg.format(obj=obj))
        return redirect(self.index_url)
