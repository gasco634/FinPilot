# Moteur d’alertes FinPilot

Les alertes sont recalculées à l’ouverture du tableau de bord, pour le compte entier même si un filtre d’activité ou de client est choisi. Chaque signal contient sa gravité, les montants utilisés, son explication et une action recommandée.

| Règle | Déclenchement par défaut | Estimation et action |
|---|---|---|
| Facture en retard | Solde restant après l’échéance | Solde calculé après paiements partiels; relancer le client. |
| Dépendance client | Le premier client dépasse 40 % des encaissements du mois | Diversifier le portefeuille. |
| Hausse de dépenses | Une catégorie dépasse de 30 % la moyenne des trois mois précédents | L’écart avec cette moyenne sert d’ordre de grandeur pour une économie possible. |
| Charge récurrente à confirmer | Dépense récurrente d’au moins 25 000 FCFA par mois | Le coût annuel est annualisé; l’utilisateur confirme lui-même l’utilité du service. |
| Hausse d’un abonnement | Le tarif dépasse de 20 % le dernier montant généré | Comparer le tarif et demander une autre offre. |
| Marge par activité | Baisse d’au moins 15 points entre le mois précédent et le mois en cours | Le calcul utilise les transactions reçues; vérifier temps passé, coûts et prix. |
| Tension de trésorerie | Projection négative dans les deux prochains mois au burn rate récent | Réduire les sorties non essentielles et accélérer les encaissements. |
| Objectif mensuel | Au-delà du 20 du mois, moins de la moitié de l’objectif est encaissée | Relancer les clients et prioriser les offres rentables. |
| Activité à développer | Activité positive avec au moins 100 000 FCFA encaissés sur trois mois | FinPilot classe les activités par marge nette; tester une hausse de capacité puis mesurer. |
| Économies potentielles | L’écart à la moyenne dépasse 10 000 FCFA | L’estimation additionne les écarts des catégories en hausse; les achats et la moyenne doivent être vérifiés avant d’agir. |

Les seuils présents dans l’interface sont modifiables. Les règles peuvent être désactivées séparément. Une alerte examinée ne se duplique pas à chaque chargement; les signaux périodiques reçoivent une nouvelle clé au mois suivant. Une alerte active est automatiquement résolue quand sa condition n’est plus détectée.

Les règles ne déduisent pas l’usage réel d’un abonnement ni la causalité d’une baisse de marge. Les « économies potentielles » et les recommandations de croissance sont des repères heuristiques à confirmer par l’entrepreneur.
