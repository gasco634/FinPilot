# Dictionnaire de données

Les clés primaires sont des UUID stockés en chaîne de 36 caractères. Tous les enregistrements métier sont isolés par `user_id`, sauf les tables de lignes, qui héritent de la propriété de leur devis ou facture.

| Table | Rôle | Champs principaux |
|---|---|---|
| `users` | Compte et authentification | `email` unique, `password_hash` bcrypt, `created_at` |
| `activities` | Sources d’activité | `name`, `color`, `is_active` |
| `clients` | CRM financier | `name`, coordonnées, `payment_terms_days`, note de fiabilité 1–5, `notes` |
| `categories` | Classification des flux | `name`, `kind` income/expense, `cost_type` fixed/variable/direct, `parent_id` |
| `transactions` | Flux de caisse saisis ou prévus | `kind`, `amount_xof` positif, `transaction_date`, `due_date`, `status`, méthode, client/activité/catégorie, référence et source |
| `quotes` | En-têtes de devis | numéro, client, activité, statut, date d’émission et d’acceptation, échéance de validité, sous-total, taxe, total, notes |
| `quote_items` | Lignes immuables de devis | désignation, quantité, prix unitaire FCFA, remise FCFA, taux TVA |
| `invoices` | Factures et créances | numéro, client, devis source, statut, dates, totaux |
| `invoice_items` | Copie des lignes facturées | désignation, quantité, prix unitaire, remise, taxe |
| `payments` | Règlements partiels ou complets | facture, transaction générée, montant, date et moyen de paiement |
| `budgets` | Objectifs de dépense | catégorie, activité facultative, dates de période, montant |
| `alert_rules` | Seuils configurables | type, paramètres JSON, activation |
| `alerts` | Alertes calculées | gravité, état, texte chiffré, recommandation, détails JSON, clé anti-doublon |
| `settings` | Préférences de compte | devise, thème, objectifs, identité et mentions légales en JSON |
| `recurring_rules` | Modèles d’opérations répétées | montant, catégorie, activité, fréquence, prochaine exécution |
| `attachments` | Métadonnées de pièces jointes | transaction, nom de fichier, chemin local et type MIME |
| `work_sessions` | Temps et revenus par prestation | activité, client, type de service, date, heures, revenu déclaré |

## Conventions

- `amount_xof`, `total_xof`, `unit_price_xof` et `discount_xof` sont des entiers en FCFA.
- `quantity`, `tax_rate` et `hours` sont des décimaux.
- Les statuts de transaction sont `received`, `pending` et `overdue`; les statuts de devis sont `draft`, `sent`, `accepted`, `rejected` et `expired`.
- `transactions.source` distingue `manual`, `invoice_payment` et `recurring`. Un règlement de facture est modifiable depuis sa facture pour maintenir la cohérence entre paiement et mouvement.
- `settings.preferences.fx_rate` est le taux manuel en FCFA par unité de devise d’affichage. Les valeurs source restent enregistrées en XOF ; aucune cotation de change externe n’est chargée.
- `settings.value` et les colonnes `parameters`/`details` sont des objets JSON validés au niveau API.

