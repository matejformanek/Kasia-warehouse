# Owner's request

This file captures the original ask from Petr, the owner of Kasia vera s.r.o.,
in his own words. The Czech version is the source of truth — the English
translation is for non-Czech readers and the interpretation notes are our
working assumptions, not his.

## Czech (verbatim)

> Ahoj, potřeboval bych něco jednoduchého, čím bych si konečně udělal pořádek
> ve skladech. Máme dvě pobočky, jednu v Týništi nad Orlicí a druhou
> v Sezimově Ústí, a v každé z nich se nám denně něco přijímá a něco vydává.
> Ríčany bych do toho zatím netahal, tam zboží dlouho neleží.
>
> Chtěl bych, aby šlo na pobočce zaevidovat příjem zboží a hlavně výdej —
> a aby z toho výdeje rovnou vypadl dodací list jako PDF, který by se mi
> automaticky poslal mailem, mně i Karolíně. Ona to potom posílá dál účetní.
> Bez toho mailu to nemá smysl, dneska to děláme ručně a polovina dodáků se
> zapomene přeposlat.
>
> Chce to počítat s tím, že máme různá balení — někdy prodáváme po kilech,
> někdy po sto gramech, někdy po pětadvacetikilových pytlech. A taky máme
> směsi, jako třeba Zlaté Kuře, které si sami mícháme z více koření.
> Jak to v tom systému zachytit, nechám na vás, ale počítejte s tím, že to
> tam musí být.
>
> A poslední věc — chci mít možnost cokoliv historicky opravit. Stane se,
> že někdo něco špatně naťuká, nebo se najde manko a my musíme srovnat papír
> s realitou. Bez toho se neobejdeme. Ale ať je vidět, kdo co změnil a kdy,
> ať si tam nikdo nedělá pořádek po svém.
>
> Holky na pobočkách to musí zvládnout bez školení. Karolína má mít přístup
> ke všemu jako já.

## English translation

> Hi, I need something simple to finally get the warehouses in order. We have
> two branches, one in Týniště nad Orlicí and one in Sezimovo Ústí, and every
> day something is received and something is issued in each of them. I would
> leave Říčany out of it for now — goods don't sit there for long.
>
> I'd like it to be possible at a branch to record goods receipt and
> especially goods issue — and for the issue to immediately produce a dodací
> list as a PDF, which would be automatically emailed to me and to Karolína.
> She then forwards it to the accountant. Without that email it makes no
> sense; today we do it by hand and half the dodáky get forgotten and never
> forwarded.
>
> It has to deal with the fact that we have various pack sizes — sometimes we
> sell by the kilo, sometimes by the hundred grams, sometimes in 25 kg sacks.
> And we also have mixtures, like for example Zlaté Kuře, which we blend
> ourselves from several spices. How to capture that in the system I'll leave
> to you, but count on it having to be there.
>
> And the last thing — I want to be able to historically correct anything.
> It happens that someone keys something in wrong, or a shortage shows up and
> we have to reconcile paper with reality. We can't do without it. But it has
> to be visible who changed what and when, so nobody starts tidying up on
> their own.
>
> The girls at the branches have to be able to handle it without training.
> Karolína gets the same access as me.

## Interpretation notes

What we read between the lines of the ask:

- **He wants something simple, not enterprise.** "Něco jednoduchého" is the
  first sentence. Anything that looks like SAP or even a fully featured ERP
  module is wrong for this ask. He has rejected complexity before; we will
  not earn trust by reintroducing it.
- **Two branches, not three, are in scope for stock.** Říčany HQ is
  explicitly out — not because it is unimportant, but because raw goods don't
  dwell there long enough for inventory tracking to add value. The system
  treats Říčany as a destination for outbound transfers but does not hold
  stock figures for it. See [`warehouses.md`](./warehouses.md).
- **He trusts Karolína with full access.** "Karolína má mít přístup ke všemu
  jako já." She is co-admin, owner-equivalent in the system. This is a
  business signal, not a technical one — do not water it down with finer
  permissions on her account.
- **The dodací list email is load-bearing.** Without it, the workflow does
  not close: the accountant never gets fed. Today they manage with manual
  forwarding and admit that half the dodáky get lost. The email is not a
  nice-to-have integration; it is the deliverable.
- **Correction-with-audit matters because real inventory drifts.** Real
  warehouses develop drift between records and what is on the shelf —
  miskeyed entries, shrinkage, manka. He needs the system to *let him fix
  it* without that becoming a back door for fraud. Hence audit trail: who,
  when, what before, what after, why.
- **Pack sizes and mixtures are flagged as hard, not solved.** He uses the
  words "různá balení" and "směsi" deliberately and hands the modelling back
  to us. This is the explicit invitation to think and propose, not to assume.
  See [`product-ideology.md`](./product-ideology.md).
- **"Bez školení."** Branch staff are not power users. Screens must be
  legible to someone seeing them for the first time. This is a constraint on
  every screen design in [`screens/`](./screens/).
