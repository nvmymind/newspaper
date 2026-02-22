# 신문 사설 모음

여러 신문사의 사설을 한곳에서 모아 보고, **날짜별**로 조회할 수 있는 웹 서비스입니다.

## 기능

- **사설 수집**: [네이버 뉴스 오피니언 > 사설](https://news.naver.com/opinion/editorial) 코너에서 **모든 신문사** 사설을 한 번에 수집 (조선·동아·한겨레·경향·중앙·매일경제·한국경제·연합뉴스·문화일보·세계일보 등)
- **날짜별 보기**: 당일뿐 아니라 과거 날짜의 사설도 조회 (네이버 날짜 파라미터 사용)
- **원문 링크**: 각 항목 클릭 시 네이버 뉴스 기사 페이지로 이동

## 설치 및 실행

### 1. 가상환경 (권장)

```bash
cd c:\newspaper
python -m venv venv
venv\Scripts\activate
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

- **사설 전체 수집**(네이버에 보이는 70건 안팎)을 위해 Playwright용 Chromium을 설치해 두면 좋습니다.  
  `pip install` 후 한 번만 실행: `playwright install chromium`  
  - Playwright·Chromium이 **없는 환경**(예: Railway 등 서버)에서는 네이버가 처음에 20~25개만 HTML로 내려주고 나머지는 스크롤 시에만 로드하므로, **약 25건**만 수집될 수 있습니다. 70건에 가깝게 보려면 로컬처럼 Chromium을 설치한 환경에서 실행하세요.

### 3. 서버 실행

프로젝트 폴더에서:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

브라우저에서 **http://127.0.0.1:8000** 으로 접속합니다.

- **WinError 10013** (포트 접근 거부)이 나오면 포트가 사용 중이므로 `--port 8001` 또는 `--port 8080`으로 바꿔 실행한 뒤, 주소도 `:8001` 또는 `:8080`으로 접속하면 됩니다.

### 4. 사설 조회

- 날짜를 선택하면 **해당 날짜**의 사설을 네이버 오피니언 사설 코너에서 불러옵니다.
- **과거 날짜**도 선택하면 그날 수록된 사설 목록을 조회할 수 있습니다.

## 데이터 저장 위치

- SQLite DB: `data/editorials.db` (프로젝트 폴더 안에 자동 생성)

## 코드 수정 후 웹사이트에 반영하기 (Railway / Render)

신문사를 추가하거나 기능을 수정한 뒤, **실제 웹사이트(운영 중인 서비스)에 적용**하려면 아래만 하면 됩니다. 별도로 서버에 접속하거나 FTP로 올릴 필요 없습니다.

### 1. 로컬에서 수정

- 신문사 추가: `app/scrapers/` 에 새 스크래퍼 추가 후 `app/scrapers/__init__.py` 의 `SCRAPERS` 에 등록
- 기능 추가: 해당하는 `app/` 또는 `templates/` 파일 수정

### 2. GitHub에 올리기 (push)

터미널(PowerShell 등)에서 프로젝트 폴더로 이동한 뒤:

```powershell
cd c:\newspaper
git add .
git commit -m "신문사 OOO 추가"   # 또는 "기능 설명" 처럼 변경 내용 요약
git push
```

### 3. 자동 배포

- **Railway** 또는 **Render** 는 GitHub 저장소와 연결되어 있으므로, `git push` 가 되면 **자동으로 새 배포**를 시작합니다.
- Railway/ Render 대시보드의 **Deployments** 에서 빌드가 진행되고, 몇 분 뒤 **실제 웹사이트에 반영**됩니다.
- 별도로 “배포” 버튼을 누르거나 서버에 접속할 필요 없습니다.

**정리:** 로컬에서 수정 → `git add` / `commit` / `push` → GitHub에 올라가면 Railway·Render가 알아서 재배포 → 웹사이트에 적용됨.

## API

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/editorials?date=YYYY-MM-DD&source=신문사명` | 사설 목록 (날짜·신문사 필터, 페이징) |
| GET | `/api/dates` | 사설이 저장된 날짜 목록 |
| GET | `/api/sources` | 저장된 신문사(소스) 목록 |
| POST | `/api/fetch` | 모든 신문사에서 사설 수집 실행 |

## 스크래퍼 추가 방법

1. `app/scrapers/` 아래에 새 파일 추가 (예: `khan.py`)
2. `BaseScraper` 상속, `source_name`, `list_url` 설정 후 `fetch_editorials()` 구현
3. `app/scrapers/__init__.py` 의 `SCRAPERS` 리스트에 해당 클래스 추가

각 신문사 사이트 구조가 바뀌면 해당 스크래퍼의 선택자만 수정하면 됩니다.

## 웹호스팅 업체 추천 (저렴·쉬운 설치)

이 앱은 **Python(FastAPI)** 이라서 일반 PHP 호스팅에는 올릴 수 없고, 아래처럼 **Python을 지원하는 서비스**를 쓰는 것이 좋습니다.

| 서비스 | 비용 | 난이도 | 데이터 유지 | 추천 용도 |
|--------|------|--------|-------------|-----------|
| **Render** | 무료 티어 있음 (유료는 $7/월~) | ★ 쉬움 | 무료 플랜은 **재시작 시 DB 초기화** | 테스트·데모, 처음 배포 연습 |
| **Railway** | 체험 $5 + 월 $1 무료 크레딧, 이후 사용량 과금 | ★ 쉬움 | 볼륨으로 **DB 유지 가능** | 소규모 실제 서비스 |
| **Oracle Cloud** | 항상 무료 VPS (1~2대) | ★★ 보통 | 서버 디스크에 저장 | 장기·무료로 쭉 쓰고 싶을 때 |

### 1) Render (가장 쉬움, 무료로 체험)

- **장점**: 가입 후 GitHub 저장소만 연결하면 자동 빌드·배포. 설정이 단순함.
- **단점**: 무료 플랜은 15분 동안 접속 없으면 슬립 → 다음 접속 시 수십 초 대기. **무료 플랜에서는 디스크가 비휘발성이라 재배포/재시작 시 SQLite DB가 초기화됨** (사설 수집 데이터가 안 남음).
- **적합**: “일단 인터넷에 올려서 동작만 확인해 보고 싶을 때”, 데모·테스트용.
- **절차 요약**: [render.com](https://render.com) 가입 → New → Web Service → GitHub에서 이 저장소 연결 → Build Command: `pip install -r requirements.txt` / Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` → Free 인스턴스 선택 → Deploy.

### 2) Railway (쉬움, 데이터 유지 가능)

- **장점**: GitHub 연결해서 배포 간단. **볼륨(Volume)** 을 붙이면 `/app/data` 에 SQLite를 두어 **수집한 사설 데이터가 유지**됨.
- **단점**: 무료 체험 $5 소진 후에는 사용량만큼 과금(소규모면 월 $1 무료 크레딧으로도 얼마간 가능).
- **적합**: “집 밖에서도 계속 쓰고, 수집한 날짜/기사가 쌓이게 하고 싶을 때” 소규모 서비스.
- **절차 요약**: [railway.app](https://railway.app) 가입 → New Project → GitHub에서 이 저장소 Deploy → 서비스 설정에서 **Volume** 추가, 마운트 경로 `/app/data` → Networking에서 **Generate Domain**으로 접속 URL 생성.
- **상세 단계**: [docs/RAILWAY_DEPLOY.md](docs/RAILWAY_DEPLOY.md) 에 가입부터 접속까지 차근차근 정리해 두었습니다.

### 3) Oracle Cloud Free Tier (가장 저렴한 장기 운영)

- **장점**: **항상 무료** VM 1~2대 제공. 한 번 설정해 두면 서버를 계속 켜 둘 수 있어 **장기적으로 비용 0원**에 가깝게 쓸 수 있음.
- **단점**: VM 생성·SSH·방화벽·Python 설치 등을 직접 해야 해서 **난이도는 Render/Railway보다 높음**.
- **적합**: “비용 없이 계속 켜 두고 싶다” / “VPS를 직접 다뤄도 된다” 할 때.
- **절차 요약**: Oracle Cloud 가입 → Always Free VM 생성(Ubuntu 등) → SSH 접속 후 이 저장소 clone → `python3 -m venv venv` / `pip install -r requirements.txt` / `uvicorn app.main:app --host 0.0.0.0 --port 8000` 실행. (systemd 등록하면 재부팅 후에도 자동 실행 가능.)

---

**한 줄 정리**

- **가장 쉽게** 올려보고 싶다 → **Render** (무료, 단 DB는 무료 플랜에서 유지 안 됨).
- **쉽게 올리면서 데이터도 유지**하고 싶다 → **Railway** (볼륨 연결해서 사용).
- **비용 없이 오래 켜 두고 싶다** → **Oracle Cloud Free Tier** (설정은 조금 더 필요).

## Cafe24에 올려서 웹서비스 하기

**가능 여부**

- **일반 웹호스팅(뉴아우토반, 홈페이지 호스팅)**: PHP/MySQL만 지원하므로 **이 프로젝트(Python/FastAPI)는 올릴 수 없습니다.**
- **가상서버호스팅(VPS)** 또는 **단독서버호스팅**: 서버 권한으로 Python을 설치할 수 있어 **이 프로젝트를 올려 웹서비스를 할 수 있습니다.**

즉, Cafe24에서 이 앱을 서비스하려면 **가상서버호스팅(VPS) 이상**을 신청해야 합니다.

### VPS에서 배포 절차 요약

1. **Cafe24 가상서버호스팅 신청** 후 SSH로 서버 접속
2. **서버 환경 구성**
   - Python 3.10+ 설치 (`python3`, `python3-venv`, `pip`)
   - (선택) Nginx 설치 후 리버스 프록시 설정
3. **프로젝트 올리기**
   - 이 저장소를 `git clone` 하거나, `app/`, `templates/`, `requirements.txt` 등 필요한 파일을 서버로 업로드
4. **실행**
   ```bash
   cd /경로/newspaper
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
5. **항상 켜 두기**  
   `systemd` 등으로 서비스 등록해 재부팅 후에도 자동 실행되게 설정하는 것을 권장합니다.

데이터는 서버의 `data/editorials.db`(SQLite)에 저장됩니다. VPS 사양은 경량이면 1 vCPU, 1~2GB RAM으로도 동작 가능합니다.

## Synology NAS에 설치하기 (Docker)

**가능 여부**: Synology NAS에서 **Container Manager(Docker)**를 지원하는 모델이면 이 앱을 Docker로 올려서 웹서비스할 수 있습니다.

### DS1517 등: 패키지 센터에 Docker/Container Manager가 없는 경우

**Package Center에 Docker나 Container Manager가 안 보인다면**, 해당 NAS는 **공식적으로 Docker 패키지를 지원하지 않는 모델**입니다. DS1517, DS1515 등 일부 구형·일부 시리즈는 시놀로지에서 Docker/Container Manager를 제공하지 않아 패키지 센터에 목록이 없습니다.  
이 경우 **NAS 위에서는 이 앱을 Docker로 돌릴 수 없으므로**, 아래 대안 중 하나를 쓰는 것이 좋습니다.

**대안 1 – 같은 집/사무실 PC에서 실행 (가장 간단)**  
- 이 프로젝트를 **Windows/Mac/리눅스 PC**에 두고, `uvicorn app.main:app --host 0.0.0.0 --port 8000` 으로 실행합니다.  
- 같은 네트워크의 다른 기기(휴대폰, NAS 브라우저 등)에서 **`http://PC의IP:8000`** 으로 접속해 사용합니다.  
- PC만 켜 두면 NAS 없이도 “집 안에서만” 서비스 가능합니다.

**대안 2 – 클라우드/호스팅 사용**  
- **Render**, **Railway**, **Oracle Cloud Free Tier** 등(위 “웹호스팅 업체 추천” 참고)에 배포하면, NAS와 상관없이 인터넷에서 접속할 수 있습니다.

**대안 3 – 다른 장비 (Raspberry Pi, 구형 노트북 등)**  
- 라즈베리 파이나 사용하지 않는 PC에 Linux를 설치한 뒤, 이 프로젝트를 설치해 같은 방식으로 `uvicorn` 실행 후 `http://해당기기IP:8000` 으로 접속해 사용할 수 있습니다.

정리하면, **NAS 패키지 센터에 Docker가 없는 모델에서는 이 앱을 NAS 안에 직접 설치하는 것은 어렵고**, 같은 네트워크의 PC나 클라우드 등 **다른 장비에 올려서 쓰는 방식**을 권장합니다.

### 요구사항

- DSM 6.x 또는 7.x, **Docker** 또는 **Container Manager** 패키지 설치됨
- Intel/AMD 64비트(x86_64) CPU 탑재 모델 (DS1517, Plus 시리즈 등)

### 방법 1: Docker Compose로 실행 (권장)

1. **프로젝트를 NAS에 올리기**  
   File Station이나 공유폴더에 `newspaper` 폴더 전체를 복사(예: `docker/newspaper`).

2. **Container Manager** 실행 → **프로젝트** 탭 → **생성** → **경로**에 위 폴더 선택.

3. **docker-compose.yml**이 있는 디렉터리를 선택한 뒤, **다음**으로 진행해 프로젝트 생성 및 실행.

4. **포트**  
   - 컨테이너 포트 8000을 NAS 포트 8000(또는 원하는 포트)에 연결해 두면,  
     `http://NAS주소:8000` 으로 접속 가능합니다.

5. **데이터 유지**  
   - `docker-compose.yml`에서 `./data`를 `/app/data`에 마운트해 두었으므로,  
     NAS의 해당 폴더에 DB(`editorials.db`)가 저장되고, 컨테이너를 지워도 데이터는 남습니다.

### 방법 2: 이미지 빌드 후 컨테이너만 실행

- PC에서 `docker build -t newspaper .` 로 이미지 빌드 후,  
  Docker Hub나 NAS로 이미지를 옮기고, Container Manager에서 **이미지** → 해당 이미지로 **실행**.
- 실행 시 **볼륨**에 호스트 폴더(예: `/docker/newspaper/data`) → 컨테이너 경로 `/app/data` 연결.
- **포트** 8000:8000 설정.

### 접속 주소

- 같은 네트워크: `http://NAS의IP:8000`
- (선택) DSM **제어판 → 로그인 포털 → 응용 프로그램**에서 포트 8000을 등록하면 DSM 메뉴에서 바로 열 수 있습니다.

## 주의사항

- 수집은 해당 사이트의 목록 페이지 구조에 의존합니다. 사이트 개편 시 선택자 수정이 필요할 수 있습니다.
- 과도한 요청을 피하기 위해 수집은 하루에 몇 번 정도만 실행하는 것을 권장합니다.
