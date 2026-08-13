# Parser fix v4

PVL reservoir detail pages contain two different datasets:

1. Historical table:
   Datum | Hladina | Odtok | Q N

2. Current values block:
   Hladina vody v nádrži
   Objem
   Přítok
   Odtok

The previous parser treated historical rows as if they contained volume and inflow,
which produced values such as 13.08 from the date.

v4 strictly separates both sections.
Historical `series` now contains only:
- timestamp
- level
- outflow

Current values contain:
- timestamp
- level
- volume
- inflow
- outflow
