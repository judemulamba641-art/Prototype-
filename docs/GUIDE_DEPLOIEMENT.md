# GUIDE DE DÉPLOIEMENT - WAY Platform v2.4

## Prérequis

- Docker & Docker Compose
- 4GB RAM minimum
- 2 CPU cores

## Déploiement Local (Développement)

```bash
# 1. Cloner le projet
cd way_optimized/backend

# 2. Configuration
cp .env.example .env
# Éditer .env avec vos valeurs

# 3. Lancer les services
docker-compose up -d

# 4. Migrations et superuser
docker-compose exec app python manage.py migrate
docker-compose exec app python manage.py createsuperuser

# 5. Accès
# API: http://localhost:8000/api/
# Docs: http://localhost:8000/api/docs/
# Admin: http://localhost:8000/admin/
```

## Déploiement Production

### 1. Infrastructure Cloud

```bash
# AWS/GCP/Azure
# 1. Créer une instance avec Docker
# 2. Configurer le security group (ports 80, 443, 8000)
# 3. Configurer le domaine et SSL

# 4. Déployer
git clone <repo>
cd way_optimized/backend
cp .env.example .env
# Éditer .env avec les secrets de production

docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 2. Configuration Production

```env
DEBUG=False
SECRET_KEY=<strong-random-key>
DATABASE_URL=postgresql://way:<password>@<host>:5432/way_db
REDIS_URL=redis://<host>:6379/0
JWT_SECRET=<strong-jwt-secret>
ENCRYPTION_KEY=<32-bytes-key>

# Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Payments
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Storage
STORAGE_BACKEND=s3
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=way-storage
```

### 3. SSL/TLS

```bash
# Avec Let's Encrypt et NGINX
# docker-compose.yml additionnel
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
```

### 4. Monitoring

```bash
# Prometheus + Grafana (optionnel)
docker-compose -f docker-compose.monitoring.yml up -d

# Ou utiliser le endpoint /api/metrics/ pour Prometheus
```

### 5. Backup

```bash
# Automatique via Celery beat
# Ou manuel:
docker-compose exec app python manage.py dumpdata > backup.json

# PostgreSQL
docker-compose exec postgres pg_dump -U way way_db > backup.sql
```

## Scaling Horizontal

```bash
# 1. Load Balancer (NGINX/HAProxy)
# 2. Multiple app instances
docker-compose up -d --scale app=3

# 3. Redis Cluster
# 4. PostgreSQL Primary-Replica
```

## Vérification Post-Déploiement

```bash
# 1. Health check
curl https://your-domain.com/api/health/

# 2. API docs
curl https://your-domain.com/api/docs/

# 3. Test auth
curl -X POST https://your-domain.com/api/auth/register/   -H "Content-Type: application/json"   -d '{"email":"test@way.com","username":"test","password":"Test123!","confirm_password":"Test123!"}'

# 4. Test execution
curl -X POST https://your-domain.com/api/core/executions/   -H "Authorization: Bearer <token>"   -H "Content-Type: application/json"   -d '{"skill_id":"<skill-id>","input_data":{"prompt":"test"}}'
```

## Troubleshooting

### Problèmes courants

1. **Database connection failed**
   - Vérifier DB_HOST et DB_PORT
   - Vérifier que PostgreSQL est démarré

2. **Redis connection failed**
   - Vérifier REDIS_URL
   - Vérifier que Redis est démarré

3. **Celery workers ne démarrent pas**
   - Vérifier CELERY_BROKER_URL
   - Vérifier que Redis est accessible

4. **Static files 404**
   - Lancer `python manage.py collectstatic`
   - Vérifier STATIC_ROOT

5. **Rate limit exceeded**
   - Attendre 60 secondes
   - Vérifier RATE_LIMIT dans .env

## Support

Pour plus d'informations, consulter:
- README.md
- docs/RAPPORT_ARCHITECTURE.md
- docs/RAPPORT_SECURITE.md
- docs/RAPPORT_PERFORMANCE.md
