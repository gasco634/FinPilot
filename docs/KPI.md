# Définitions des KPI

Tous les montants sont stockés en entiers FCFA. Les filtres de dates sont inclusifs. Les chiffres de trésorerie excluent les lignes en attente et en retard jusqu'à leur règlement.

| Indicateur | Définition FinPilot |
|---|---|
| CA encaissé | Somme des transactions de type revenu au statut reçu sur la période. Les paiements de facture y entrent une seule fois via la transaction liée. |
| CA facturé | Somme du total des factures émises dans la période, hors brouillons et annulations. |
| Marge brute | CA encaissé moins les dépenses classées comme coûts directs. |
| Marge brute % | Marge brute / CA encaissé × 100. Zéro si le CA est nul. |
| Dépenses | Somme des transactions de type dépense au statut reçu sur la période. |
| Résultat net de trésorerie | CA encaissé moins dépenses payées. C’est un indicateur de trésorerie, pas un résultat comptable d’engagement. |
| Marge nette % | Résultat net de trésorerie / CA encaissé × 100. |
| Taux d’épargne | Résultat net de trésorerie / CA encaissé × 100. Utilise la même base de caisse que la marge nette dans cette première version. |
| Trésorerie | Encaissements reçus moins dépenses payées depuis le début de l’historique jusqu’à la fin de la période. Pas de rapprochement bancaire. |
| Créances | Total des factures non annulées moins tous les paiements associés, plancher zéro par facture. |
| DSO | Moyenne pondérée par les paiements reçus pendant la période filtrée du nombre de jours entre l’émission de facture et le règlement. |
| Taux de recouvrement | Paiements reçus pendant la période / factures émises pendant la période × 100. Ce ratio de période peut dépasser 100 % lorsque des factures anciennes sont encaissées. |
| Conversion devis | Devis acceptés / devis envoyés, acceptés, refusés ou expirés émis pendant la période × 100. Les brouillons sont exclus. |
| Délai moyen d’acceptation | Moyenne des jours entre l’émission et l’acceptation des devis acceptés de la période, si la date d’acceptation a été enregistrée. |
| Panier moyen | CA encaissé / nombre de transactions de revenu reçues sur la période. |
| Concentration client | Encaissements du client principal / encaissements totaux × 100. Les revenus sans client sont regroupés. |
| HHI client | Somme des carrés des parts de CA client exprimées en pourcentage. |
| Croissance MoM | Variation du CA encaissé entre la période filtrée et la période précédente de durée identique. |
| Croissance YoY | Variation du CA encaissé vs la même période un an plus tôt, lorsque l’historique existe. |
| Burn rate | Moyenne des dépenses mensuelles reçues sur les trois mois affichés dans l’historique. |
| Runway | Trésorerie divisée par burn rate mensuel. Non défini si le burn rate vaut zéro. |
| Point mort | Charges fixes payées / taux de marge sur coûts variables payés. Les catégories doivent être typées fixe ou variable/direct. |
| Revenu horaire | Revenu d’une activité / heures saisies sur cette activité pour la période. Non affiché sans saisie d’heures. |

## Hypothèses et limites

- Le « bénéfice net » présenté dans le cockpit est un résultat de caisse simplifié. Il ne remplace pas un bilan comptable ou fiscal.
- L’application ne calcule pas encore la TVA récupérable, les amortissements, les impôts ni les charges sociales.
- Les factures sont suivies séparément des transactions. Les opérations non facturées doivent être saisies directement dans le registre.
- La prévision utilise la moyenne des trois derniers mois disponibles et un multiplicateur de scénario : 1,15 en optimiste, 1,00 en réaliste et 0,80 en pessimiste. Avec douze mois d’historique, elle applique aussi un facteur saisonnier à partir du même mois l’année précédente, borné entre -12,5 % et +12,5 %. Elle n’intègre pas le calendrier exact des factures attendues.
- Les dépenses ne sont affectées à une activité ou à un client que si l’utilisateur les renseigne ; sans cela elles apparaissent « Non affecté ».
- La conversion des devis et le DSO respectent les dates de la période filtrée. Une même facture peut recevoir plusieurs paiements ; le DSO est pondéré par les montants encaissés pendant cette période.
- Les gains potentiels des alertes d’économies correspondent aux dépenses du dernier mois observé au-dessus de la moyenne des trois mois calendaires précédents. Il s’agit d’une estimation à vérifier, pas d’une économie garantie.
