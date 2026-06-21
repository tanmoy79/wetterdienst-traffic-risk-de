# Reference data

## `bbsr_kreistypen_2020.csv` — settlement-structure district types

Classification of every German district (Kreis) into a *siedlungsstruktureller
Kreistyp* (settlement-structure district type), used to label accidents as
**urban** or **rural** for RQ1.

| Kreistyp code | Name | Urban/rural |
| --- | --- | --- |
| 1 | kreisfreie Großstadt (independent large city) | urban |
| 2 | Städtischer Kreis (urban district) | urban |
| 3 | Ländlicher Kreis mit Verdichtungsansätzen (rural with density) | rural |
| 4 | Dünn besiedelter ländlicher Kreis (sparsely populated rural) | rural |

The first five digits of the district key (`Kennziffer`) are the
`ULAND`+`UREGBEZ`+`UKREIS` code, which lets us join the classification onto
each accident.

**Source:** Bundesinstitut für Bau-, Stadt- und Raumforschung (BBSR),
Laufende Raumbeobachtung – Raumabgrenzungen, *Siedlungsstrukturelle Kreistypen
2020*.
<https://www.bbsr.bund.de/BBSR/DE/forschung/raumbeobachtung/Raumabgrenzungen/deutschland/kreise/siedlungsstrukturelle-kreistypen/siedlungsstrukt-kreistypen-2020.csv>

**Licence:** Open data — GovData lists this dataset as *free use* (data
provider: Federal Ministry of the Interior and Community, via the BBSR),
see <https://www.govdata.de/suche/daten/siedlungsstrukturelle-kreistypen>.
Attribution: © BBSR Bonn. (Before formal publication, confirm the exact
licence label on the GovData metadata for the vintage you cite.)
