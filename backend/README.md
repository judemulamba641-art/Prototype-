# WAY Platform v2.4 - Optimized Backend

## Architecture

WAY Platform est une architecture backend modulaire optimisée, 10x plus légère que l'original tout en conservant 100% des fonctionnalités.

### Apps Django (6 au lieu de 40)

| App | Modules Fusionnés |
|-----|------------------|
| `way_core` | Core + Runtime + SDK + Registry + Sandbox |
| `way_identity` | Users + Auth + Permissions + Device + JWT |
| `way_finance` | Credits + Wallets + Payments + Billing + Transfers |
| `way_skills` | Skills + Marketplace + Providers + Pricing + Router |
| `way_infra` | Cache + Storage + Events + Telemetry + Audit + Backup |
| `way_ops` | Admin + Notifications + Groups + Rate Limiting |

### Services Externes (3 au lieu de 8)

- **PostgreSQL** - Database principale
- **Redis** - Cache + Pub/Sub + Rate Limiting
- **Celery** - Task queue (optionnel)

### Event Bus Interne

Remplace Kafka par un système compatible PostgreSQL + Redis, prêt pour migration future.

## Démarrage Rapide

```bash
# 1. Cloner et entrer dans le projet
cd backend

# 2. Copier la configuration
cp .env.example .env

# 3. Lancer avec Docker Compose
docker-compose up -d

# 4. Créer un superuser
docker-compose exec app python manage.py createsuperuser

# 5. Accéder à l'API
# API: http://localhost:8000/api/
# Docs: http://localhost:8000/api/docs/
# Admin: http://localhost:8000/admin/
```

## Tests

```bash
# Tests complets avec couverture
pytest --cov --cov-report=html

# Tests spécifiques
pytest tests/test_identity.py
pytest tests/test_finance.py
pytest tests/test_skills.py
pytest tests/test_core.py
pytest tests/test_infra.py
```

## Sécurité

- 10 couches de sécurité (Annexe D)
- JWT avec refresh tokens
- Ed25519 signatures
- AES-256 encryption
- Rate limiting 50 req/min
- Fraud detection
- Immutable audit trail
- Device trust + biometric
- Sandbox isolation
- WAF + IP filtering

## Scalabilité

- Horizontal scaling ready
- Multi-workers Celery
- Cache layer Redis
- Provider failover automatique
- Database connection pooling
- Target: 1M+ users, 100K+ skills, 10M+ tx/day

## API Endpoints

### Auth
- `POST /api/auth/register/` - Inscription
- `POST /api/auth/login/` - Connexion
- `POST /api/auth/wallet_login/` - Auth wallet
- `POST /api/auth/refresh/` - Refresh token
- `POST /api/auth/logout/` - Déconnexion

### Users
- `GET /api/auth/users/me/` - Profil
- `PATCH /api/auth/users/me/` - Modifier profil
- `POST /api/auth/users/me/change_password/` - Changer mot de passe
- `POST /api/auth/users/me/enable_2fa/` - Activer 2FA

### Devices
- `GET /api/auth/devices/` - Liste devices
- `POST /api/auth/devices/{id}/approve/` - Approuver device
- `POST /api/auth/devices/{id}/revoke/` - Révoquer device

### Permissions
- `GET /api/auth/permissions/check/` - Vérifier permission
- `POST /api/auth/permissions/grant/` - Accorder permission
- `POST /api/auth/permissions/revoke/` - Révoquer permission

### Groups
- `GET /api/auth/groups/` - Liste groupes
- `POST /api/auth/groups/{id}/add_member/` - Ajouter membre
- `POST /api/auth/groups/{id}/remove_member/` - Retirer membre

### Wallet
- `GET /api/finance/wallets/` - Wallets
- `GET /api/finance/wallets/{id}/balance/` - Solde
- `POST /api/finance/wallets/{id}/freeze/` - Geler
- `POST /api/finance/wallets/{id}/unfreeze/` - Dégeler

### Credits
- `GET /api/finance/ledger/` - Ledger (immutable)
- `POST /api/finance/transfers/` - Transférer crédits

### Payments
- `GET /api/finance/payments/` - Paiements
- `POST /api/finance/payments/` - Créer paiement
- `POST /api/finance/payments/webhook/` - Webhook

### Billing
- `GET /api/finance/billing/` - Rapports
- `POST /api/finance/billing/generate/` - Générer rapport

### Skills
- `GET /api/core/skills/` - Liste skills
- `GET /api/core/skills/marketplace/` - Marketplace
- `POST /api/core/skills/` - Créer skill
- `POST /api/core/skills/{id}/approve/` - Approuver
- `POST /api/core/skills/{id}/suspend/` - Suspendre
- `POST /api/core/skills/{id}/install/` - Installer
- `POST /api/core/skills/{id}/estimate/` - Estimer coût

### Providers
- `GET /api/core/providers/` - Liste providers
- `GET /api/core/providers/health/` - Santé providers

### Executions
- `GET /api/core/executions/` - Exécutions
- `POST /api/core/executions/` - Exécuter skill
- `POST /api/core/executions/{id}/retry/` - Réessayer

### Registry
- `GET /api/core/registry/` - Registre global
- `POST /api/core/registry/{id}/heartbeat/` - Heartbeat

### Runtime
- `GET /api/core/runtime/` - Sessions
- `POST /api/core/runtime/` - Créer session
- `POST /api/core/runtime/{id}/start/` - Démarrer
- `POST /api/core/runtime/{id}/complete/` - Terminer
- `POST /api/core/runtime/{id}/kill/` - Tuer

### Audit
- `GET /api/infra/audit/` - Logs audit
- `GET /api/infra/audit/verify/` - Vérifier chaîne

### Events
- `GET /api/infra/events/` - Événements
- `POST /api/infra/events/process/` - Traiter

### Telemetry
- `GET /api/infra/telemetry/` - Métriques
- `GET /api/infra/telemetry/dashboard/` - Dashboard

### Cache
- `GET /api/infra/cache/stats/` - Statistiques
- `POST /api/infra/cache/invalidate/` - Invalider

### Notifications
- `GET /api/ops/notifications/` - Notifications
- `GET /api/ops/notifications/unread/` - Non lues
- `POST /api/ops/notifications/{id}/mark_read/` - Marquer lue

### Currency
- `GET /api/ops/currency/` - Taux de change
- `POST /api/ops/currency/convert/` - Convertir

## WebSocket

- `ws://localhost:8000/ws/notifications/?token=JWT` - Notifications temps réel
- `ws://localhost:8000/ws/wallet/?token=JWT` - Mises à jour wallet

## License

Proprietary - WAY Platform
