# Приватный репозиторий GitHub + деплой на VPS

Сделать репозиторий закрытым и оставить `git pull` на сервере можно за ~5 минут.

## Что нельзя сделать автоматически из Cursor

- Включить **Private** в настройках GitHub (нужен ваш вход на github.com).
- Зайти на VPS по SSH без вашего пароля.

## Порядок (рекомендуемый)

### 1. На VPS — подготовить ключ (один раз)

```bash
cd /opt/visulit
git pull origin main   # пока репо ещё public, подтянуть скрипт
bash scripts/setup_github_private_deploy_key.sh
```

Скрипт выведет **публичный ключ** (одна строка `ssh-ed25519 ...`).

### 2. На GitHub — Deploy key

1. Откройте: https://github.com/Lina0107/VisuLit/settings/keys  
2. **Add deploy key**  
3. Title: `visulit-vps`  
4. Key: вставьте строку из шага 1  
5. **Allow write access** — не включайте (достаточно read-only)  
6. **Add key**

### 3. На VPS — проверка

```bash
ssh -T git@github.com-visulit
# ожидается: Hi Lina0107/VisuLit! You've successfully authenticated...

cd /opt/visulit
git pull origin main
```

### 4. На GitHub — сделать репозиторий приватным

1. https://github.com/Lina0107/VisuLit/settings  
2. Внизу **Danger Zone** → **Change repository visibility** → **Make private**  
3. Подтвердите имя репозитория  

После этого код на GitHub видят только вы и приглашённые. Сайт **visulit.com** продолжит работать; деплой: `git pull` + `docker compose build` как раньше.

## Деплой после private

```bash
cd /opt/visulit
git pull origin main
docker compose build --no-cache frontend
docker compose up -d
```

Или: `bash scripts/deploy_vps.sh` (если `.env` на месте).

## Важно

- Файл **`.env`** по-прежнему не коммитьте в Git.  
- Приватный репо **не прячет** уже скачанные файлы на VPS — только доступ через GitHub.
