# Лабораторна робота №2 — Контейнеризація

Автор: Верезей Ілля ІМ-42
Платформа: MacBook Air M1, 16 GB RAM, macOS 15, Docker 29.4.0

---

## Python Application

Стартовий проект: python-app/ (FastAPI + uvicorn). Залежності в requirements/backend.in без версій, тому збірка не відтворювана при оновленні пакетів. Зафіксував версії через pip freeze всередині контейнера і записав у requirements.txt.

### Порядок шарів і кешування

Перший Dockerfile (Dockerfile.v1) копіює весь код до pip install. Будь-яка зміна файлу інвалідує шар з встановленням залежностей, і docker перевстановлює все з нуля.

Другий (Dockerfile.v2) спочатку копіює тільки requirements.txt і встановлює залежності, а вже потім копіює код. При зміні коду шар з pip install береться з кешу.

Як відтворити:
```
docker pull python:3.13-bookworm
docker build -f Dockerfile.v1 -t python-app:v1 . --no-cache
docker build -f Dockerfile.v2 -t python-app:v2 . --no-cache
echo "# change" >> spaceship/routers/health.py
docker build -f Dockerfile.v1 -t python-app:v1-rebuild .
docker build -f Dockerfile.v2 -t python-app:v2-rebuild .
```

| Dockerfile | Розмір | Перша збірка | Rebuild |
|---|---|---|---|
| v1 (debian, неоптимізований) | 1.54 GB | ~10.8s | ~10.0s |
| v2 (debian, оптимізований) | 1.54 GB | ~10.2s | ~0.5s |

Rebuild v2 приблизно в 20 разів швидший. Розміри однакові бо база і набір залежностей ідентичні.

### Alpine

Dockerfile.alpine — той самий Dockerfile.v2 але з FROM python:3.13-alpine.

```
docker pull python:3.13-alpine
docker build -f Dockerfile.alpine -t python-app:alpine . --no-cache
```

| Базовий образ | Розмір | Час збірки |
|---|---|---|
| python:3.13-bookworm | 1.54 GB | ~10.2s |
| python:3.13-alpine | 137 MB | ~9.8s |

Alpine в 10 разів менший. Час збірки майже однаковий — більшість часу займає pip install, а не завантаження базового образу.

### Numpy

Додав ендпоінт /api/matrix в spaceship/routers/api.py який генерує дві матриці 10х10 і перемножує їх через numpy. Порівняв alpine і debian:

```
docker build -f Dockerfile.numpy        -t python-app:numpy-alpine . --no-cache
docker build -f Dockerfile.numpy-debian -t python-app:numpy-debian . --no-cache
```

| Образ | Розмір | Час збірки |
|---|---|---|
| numpy + alpine | 225 MB | ~22.4s |
| numpy + debian | 1.62 GB | ~18.3s |

На alpine numpy збирається з вихідників бо немає готових wheel для musl/arm64. Тому час більший. На debian pip бере готовий binary wheel і все ставиться швидше. Але розмір образу в 7 разів менший у alpine.

---

## Musl vs glibc — DNS search domain

Коли контейнер отримує --dns-search, резолвер при NXDOMAIN має пробувати hostname.searchdomain.

Як відтворити:
```
docker network create dns-lab

docker run -d --name dns-server --network dns-lab \
  alpine sh -c "apk add dnsmasq -q && \
  echo 'address=/myservice.internal.corp/10.0.0.50' > /etc/dnsmasq.conf && \
  dnsmasq -k"

DNS_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' dns-server)

docker run --rm --network dns-lab --dns=$DNS_IP --dns-search="corp" \
  ubuntu:latest getent hosts myservice.internal

docker run --rm --network dns-lab --dns=$DNS_IP --dns-search="corp" \
  alpine:latest getent hosts myservice.internal
```

| Контейнер | Результат |
|---|---|
| Ubuntu (glibc) | 10.0.0.50  myservice.internal.corp |
| Alpine (musl) | (порожньо) |

З логів DNS сервера видно що Ubuntu надсилає два запити: спочатку myservice.internal (NXDOMAIN), потім myservice.internal.corp (успішно). glibc коректно застосовує search domain при NXDOMAIN.

Alpine надсилає тільки myservice.internal і не пробує з суфіксом. Причина в тому що musl реалізує DNS резолвер незалежно від glibc і не відтворює ndost-логіку та обробку searchlist. Через це у Kubernetes або Docker Swarm Alpine контейнери можуть не резолвити сервіси за короткими іменами там де Debian контейнери спрацьовують без проблем.

---

## Golang — Multi-stage builds

Стартовий проект: golang-app/ (FizzBuzz HTTP сервер, cobra + net/http).

### Single-stage (Dockerfile.basic)

```
docker pull golang:1.22-bookworm
docker build -f Dockerfile.basic -t fizzbuzz:basic . --no-cache
```

Образ 1.33 GB. Містить весь Go toolchain, кеш модулів, вихідний код. Для запуску потрібен тільки бінарник (~5 MB) і templates/index.html.

### FROM scratch (Dockerfile.scratch)

Перша стадія збирає статичний бінарник (CGO_ENABLED=0), друга — порожній образ куди копіюється тільки бінарник і templates/.

```
docker build -f Dockerfile.scratch -t fizzbuzz:scratch . --no-cache
```

Одразу виникла проблема: docker exec -it fizzbuzz:scratch sh повертає "executable file not found". В scratch немає нічого взагалі — ні shell ні ls. Дебажити контейнер неможливо.

### Distroless (Dockerfile.distroless)

Замість scratch використав gcr.io/distroless/static-debian12. Додає мінімальну файлову систему (CA-сертифікати, timezone data) без shell і пакетного менеджера.

```
docker pull gcr.io/distroless/static-debian12
docker build -f Dockerfile.distroless -t fizzbuzz:distroless . --no-cache
```

| Dockerfile | Розмір | Час збірки |
|---|---|---|
| basic (single-stage) | 1.33 GB | ~12.4s |
| scratch (multi-stage) | 10.1 MB | ~7.4s |
| distroless (multi-stage) | 16.2 MB | ~7.5s |

Multi-stage зменшує образ приблизно в 130 разів. Час збірки трохи менший бо фінальний образ не містить зайвих шарів.

---

## Swift/Vapor (практична частина)

Застосунок з лаб. №1 — Simple Inventory API на Swift/Vapor з MariaDB. Репозиторій: https://github.com/Useraccont1507/lab1devops

### Dockerfile

Multi-stage build. Перша стадія swift:6.0.1-jammy компілює бінарник зі статичною Swift stdlib (--static-swift-stdlib). Друга стадія ubuntu:22.04 з мінімальним набором бібліотек (libcurl4, libxml2, ca-certificates). Весь Swift toolchain (~1.5 GB) залишається в build-стадії, у фінальний образ копіюється тільки бінарник і Resources/.

### Docker Compose

docker-compose.yml піднімає три сервіси у відокремлених мережах:
- db: mariadb:11, дані у named volume db_data
- app: збирається з Dockerfile, залежить від db через healthcheck
- nginx: nginx:alpine, proxy 80 → app:8000

Важливий момент: без condition: service_healthy на db, застосунок стартує раніше ніж MariaDB готова і autoMigrate падає з помилкою підключення. Healthcheck вирішує цю проблему.

```
git clone https://github.com/Useraccont1507/lab1devops
cd lab1devops
docker compose up -d --build
```

---

## Висновки

1. Пінити залежності обов'язково. pip install fastapi без версії дасть різний результат через місяць. pip freeze або pip-compile фіксують точні версії.

2. Порядок шарів суттєво впливає на час rebuild. Залежності копіюються і встановлюються до коду — тоді при зміні коду pip install не запускається повторно. Виграш у 10-20 разів.

3. Alpine малий але не безкоштовний. 137 MB проти 1.54 GB — хороший результат. Але numpy і інші C-розширення збираються з вихідників (довше, потрібні build tools). І ще DNS search domain поводиться інакше ніж у glibc що може давати сюрпризи у production.

4. Multi-stage build обов'язковий для компільованих мов. 10 MB проти 1.33 GB — різниця очевидна. Build-оточення не повинно потрапляти у production образ.

5. Scratch мінімальний але незручний. Дебажити неможливо. Distroless додає лише кілька MB але дає нормальну файлову систему і CA-сертифікати. Для production distroless зручніший.
