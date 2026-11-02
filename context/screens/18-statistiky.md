# Statistiky / Analytics

## Purpose
Answers "kolik se za období spotřebovalo / vyrobilo / prodalo / přijalo" (e.g. garlic
granules used in míchání per month) without asking Matej for a query. Per
[`0107`](../decisions/0107-analytics-dashboard-chartjs.md).

## Who uses it
Vlastník only (Petr, Karolína), desktop first, responsive. Obsluha get 403.

## What it shows
- Filter bar: období (30 dní / tento měsíc / minulý měsíc / 12 měsíců / tento rok / vlastní od–do), seskupení (den / měsíc / rok), pobočka, produkty (diacritic-insensitive search).
- Tab chips: **Přehled** (KPI strip with change vs the previous period of equal length, trend příjem / míchání / prodej, top 10 produktů), **Spotřeba v míchání** (per period, stacked by surovina, by surovina, by směs), **Výdeje** (per period, odběratel, produkt, pobočka), **Příjem** (per period, dodavatel, produkt), **Dávky a lidé** (dávky per period, per směs, per uživatel, per pobočka).
- Přehled also has **Všechny produkty v čase** (GA4-style explorer): metric switch (míchání / prodej / příjem), line chart with a dotted „Celkem" line plus one line per ticked row (default top 5, at most 10), and a table of every product with „% z celku", change vs the previous period, the other two metrics, search, sorting and paging. Computed client-side from one server payload; CSV exports all products × the three metrics (current and previous period).
- Every panel: chart, table and „Stáhnout CSV" (UTF-8 BOM, `;`, comma decimals).

## What you can do here
- Change filters and press **Použít**; the URL is shareable.
- Click a bar: product charts narrow to that product, time charts narrow to that period.

## What it links to / from
- Reached from: sidebar → Správa → Statistiky.
- Goes to: itself only (drill-down is a filter change).

## Business rules & validation
- Only `status=done` movements, bucketed by `date_issued`; planned příjem never counts.
- Spotřeba v míchání = výdej to the internal Míchárna; prodej = výdej to non-internal odběratelé (inventura and převody excluded); příjem excludes the míchárna, inventura and převod legs.
- Vyrobeno / dávky = `MixingJob` in state done; cancelled and deleted dávky do not appear.
- Unlimited products (Voda, hotové výrobky — ks) are left out of every kg sum.
- A granularity that would draw more than ~400 buckets is coarsened automatically.
- Quantities display at 1 dp with the Czech comma (0061).

## States
- Empty panel: „Za zvolené období nejsou data."
- Invalid filter values fall back to the defaults; unknown CSV panel is 404.

## What this screen explicitly does NOT do
No user-defined charts, saved views, caching, ks reporting for hotové výrobky, or writes of any kind.

## Open questions for this screen
Prod data was wiped at go-live (0087), so early charts are sparse.
