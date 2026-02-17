# Liste de courses (Grocery List)

Application web de listes de courses pour usage personnel, conçue pour mobile. Plusieurs appareils peuvent ouvrir la même liste en même temps et voir les modifications en temps réel (WebSocket). L’accès se fait par URL de liste ; en production, l’accès peut être restreint par des liens secrets (voir Déploiement).

## Fonctionnalités

- Créer plusieurs listes, archiver ou supprimer une liste (glisser une ligne pour afficher Archiver / Supprimer).
- Ajouter des articles : le nom suffit ; quantité et notes sont optionnels. Les articles sont classés automatiquement par section : d’abord par mots-clés stockés en base (français), puis si besoin par un LLM (optionnel). Quand le LLM attribue une section, le nom de l’article est enregistré comme nouveau mot-clé pour les prochaines fois.
- Cocher les articles achetés, masquer les cochés pour garder la liste lisible.
- Réordonner les articles par glisser-déposer (poignée ⋮⋮) dans chaque section.
- Mise à jour en temps réel sur tous les onglets / appareils ouverts sur la même liste.

## Prérequis

- **Python** 3.10+ (recommandé 3.12).
- **Pas de Node/npm** : le frontend utilise AngularJS 1.8.2 et Bootstrap chargés depuis un CDN (ou fichiers locaux dans `static/`).
- Pour la production : **Ubuntu 24.04**, **Apache2** en reverse proxy, nom de domaine (ex. `list.example.com`).

## Installation

```bash
git clone <url-du-repo>
cd grocery_project
python3 -m venv .venv
source .venv/bin/activate   # ou .venv\Scripts\activate sur Windows
pip install -r requirements.txt
python manage.py migrate
```

Si vous hébergez AngularJS/Bootstrap en local, placez les fichiers dans `lists_app/static/` et adaptez `lists_app/templates/lists_app/index.html` pour pointer vers ces fichiers au lieu du CDN.

## Configuration

Variables d’environnement utiles :

| Variable        | Description |
|----------------|-------------|
| `DJANGO_SECRET_KEY` | Clé secrète Django (obligatoire en production). |
| `DJANGO_DEBUG` | `true` / `false` (défaut : `true`). |
| `ALLOWED_HOSTS` | Liste d’hôtes séparés par des virgules (ex. `localhost,list.example.com`). |
| `LLM_API_KEY`  | (Optionnel) Clé API pour le classement des articles par LLM (sections en français). |
| `LLM_API_URL`  | (Optionnel) URL de l’API (défaut : OpenAI). |
| `LOG_LEVEL`    | (Optionnel) Niveau de log : `WARNING` (défaut), `INFO`, `DEBUG`. Pour activer les logs informatifs ou de debug (ex. assignation de section, mots-clés appris), mettre `INFO` ou `DEBUG`. |
| `LOG_FILE`     | (Production) Chemin du fichier de log (ex. `/var/log/grocery_list/app.log`). Si défini, les logs sont aussi écrits dans ce fichier. |
| `SECRET_URL_AUTH_REQUIRED` | (Optionnel) `true` / `false` (défaut : `true`). Si `false`, l'app et l'API sont accessibles sans lien secret (développement ou si la protection est gérée autrement). |
| `REDIS_URL`    | (Optionnel) Pour production avec Redis comme channel layer (ex. `redis://localhost:6379/0`). |

En développement, une base SQLite est utilisée (`db.sqlite3` à la racine du projet).

**Mots-clés de section** : les associations mot-clé → section sont en base (modèle `SectionKeyword`). Une migration initiale remplit les mots-clés par défaut. Quand le LLM attribue une section à un article, le nom normalisé de l’article est enregistré comme nouveau mot-clé. Vous pouvez consulter ou modifier les mots-clés via l’interface d’administration Django (`/admin/`).

## Lancer en local

- **HTTP + WebSocket** (recommandé) :  
  `daphne -b 0.0.0.0 -p 8000 grocery_project.asgi:application`

- Ou le serveur de développement Django (HTTP uniquement, pas de WebSocket) :  
  `python manage.py runserver 0.0.0.0:8000`

Puis ouvrir `http://localhost:8000/` dans le navigateur (idéalement en mode mobile ou responsive).

## Tests

```bash
python manage.py test lists_app
```

Pour la qualité du code (Ruff) :

```bash
ruff check .
ruff format --check .
```

## Déploiement (Ubuntu 24.04, Apache2, list.example.com)

Procédure complète pour déployer en production avec logs dans `/var/log/grocery_list` et logrotate.

### 1. Prérequis et paquets système

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv apache2 redis-server
sudo a2enmod proxy proxy_http proxy_wstunnel ssl headers
sudo systemctl enable apache2
```

Si vous utilisez Redis comme channel layer (recommandé en production pour les WebSockets multi-processus), activez-le :

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### 2. Utilisateur et répertoires

```bash
sudo useradd -r -s /bin/false grocery
sudo mkdir -p /opt/grocery_project
sudo mkdir -p /var/log/grocery_list
sudo chown grocery:grocery /var/log/grocery_list
```

La base SQLite sera créée dans le répertoire de l’application (`/opt/grocery_project/db.sqlite3` par défaut). Pour la placer ailleurs (ex. `/var/lib/grocery_list/db.sqlite3`), créez le répertoire, donnez les droits à l’utilisateur `grocery`, et configurez `DATABASE_URL` ou adaptez `settings.py` pour utiliser un chemin d’environnement.

### 3. Déploiement de l’application

```bash
sudo -u grocery git clone <url-du-repo> /opt/grocery_project
# ou déployer les fichiers (rsync, archive, etc.) puis : sudo chown -R grocery:grocery /opt/grocery_project
cd /opt/grocery_project
sudo -u grocery python3.12 -m venv .venv
sudo -u grocery .venv/bin/pip install -r requirements.txt
sudo -u grocery .venv/bin/python manage.py migrate
sudo -u grocery .venv/bin/python manage.py collectstatic --noinput
```

### 4. Variables d’environnement

Définir au minimum pour la production :

| Variable | Exemple / description |
|----------|------------------------|
| `DJANGO_SECRET_KEY` | Clé forte (obligatoire). |
| `DJANGO_DEBUG` | `false` |
| `ALLOWED_HOSTS` | `list.example.com` |
| `LOG_LEVEL` | `WARNING` ou `INFO` |
| `LOG_FILE` | `/var/log/grocery_list/app.log` |
| `REDIS_URL` | (optionnel) `redis://127.0.0.1:6379/0` pour le channel layer |

Vous pouvez les placer dans un fichier (ex. `/etc/grocery_list/env`) et le charger dans l’unité systemd avec `EnvironmentFile=/etc/grocery_list/env`, ou les définir directement dans l’unité (voir ci-dessous).

### 5. Processus : systemd (Daphne)

Créez `/etc/systemd/system/grocery-daphne.service` :

```ini
[Unit]
Description=Grocery List Daphne ASGI
After=network.target

[Service]
Type=simple
User=grocery
Group=grocery
WorkingDirectory=/opt/grocery_project
Environment="PATH=/opt/grocery_project/.venv/bin"
EnvironmentFile=/etc/grocery_list/env
ExecStart=/opt/grocery_project/.venv/bin/daphne -b 127.0.0.1 -p 8000 grocery_project.asgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Sans fichier d’environnement, remplacez `EnvironmentFile=...` par des lignes du type :

```ini
Environment=DJANGO_SECRET_KEY=...
Environment=DJANGO_DEBUG=false
Environment=ALLOWED_HOSTS=list.example.com
Environment=LOG_FILE=/var/log/grocery_list/app.log
Environment=REDIS_URL=redis://127.0.0.1:6379/0
```

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable grocery-daphne
sudo systemctl start grocery-daphne
sudo systemctl status grocery-daphne
```

### 6. Reverse proxy Apache et SSL

Créez un virtualhost HTTPS pour votre domaine (ex. `list.example.com`). Exemple `/etc/apache2/sites-available/list.example.com.conf` :

```apache
<VirtualHost *:443>
    ServerName list.example.com
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/list.example.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/list.example.com/privkey.pem

    # Fichiers statiques
    Alias /static/ /opt/grocery_project/staticfiles/
    <Directory /opt/grocery_project/staticfiles>
        Require all granted
    </Directory>

    # WebSocket
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} websocket [NC]
    RewriteCond %{HTTP:Connection} upgrade [NC]
    RewriteRule ^/ws/(.*)$ ws://127.0.0.1:8000/ws/$1 [P,L]

    ProxyPreserveHost On
    ProxyPass /ws/ ws://127.0.0.1:8000/ws/
    ProxyPassReverse /ws/ ws://127.0.0.1:8000/ws/
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/
</VirtualHost>
```

Activez le site et redémarrez Apache :

```bash
sudo a2ensite list.example.com.conf
sudo systemctl reload apache2
```

Certificat SSL avec Certbot :

```bash
sudo apt install certbot python3-certbot-apache
sudo certbot --apache -d list.example.com
```

Certbot configure le vhost HTTPS ; complétez-le ensuite avec les directives Proxy et Alias ci-dessus si besoin.

### 7. Logs et logrotate

Les logs de l’application sont écrits dans le fichier défini par `LOG_FILE` (ex. `/var/log/grocery_list/app.log`). Le répertoire `/var/log/grocery_list` doit exister et être en écriture pour l’utilisateur `grocery` (voir étape 2).

Pour faire tourner et compresser les logs, copiez le fichier fourni dans le dépôt :

```bash
sudo cp /opt/grocery_project/deploy/logrotate.grocery-list /etc/logrotate.d/grocery-list
```

Ajustez le nom d’utilisateur/groupe dans ce fichier si vous n’utilisez pas `grocery`. Vérification :

```bash
sudo logrotate -d /etc/logrotate.d/grocery-list
```

Contenu type de `deploy/logrotate.grocery-list` : rotation quotidienne, conservation 14 jours, compression, `create 0640 grocery grocery`, `missingok`, `notifempty`.

### 8. Accès par lien secret (intégré)

L’application peut aussi être protégée par **liens secrets** : un administrateur crée des liens dans l’interface d’administration Django (modèle « Liens d’accès » / Access tokens) ; chaque lien est une URL du type `https://list.example.com/enter/TOKEN/`. Lorsqu’un utilisateur ouvre cette URL, une session est créée et il accède à l’app (listes, API, WebSocket). Il n’y a **pas d’expiration** : la session reste valide tant que le lien n’est pas révoqué. Dès qu’un administrateur révoque le lien dans l’admin, toute session créée via ce lien est invalidée (l’utilisateur est redirigé vers une page « Accès restreint » au prochain chargement).


## Licence

Usage personnel / projet démo. À adapter selon vos besoins.
