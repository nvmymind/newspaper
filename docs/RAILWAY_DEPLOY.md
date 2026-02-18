# Railway 배포 가이드 (가입부터 접속까지)

Railway 가입 후 이 프로젝트를 배포하는 순서입니다.

---

## 1단계: Railway 가입

1. 브라우저에서 **https://railway.app** 접속
2. 오른쪽 상단 **「Login」** 클릭
3. **「Login with GitHub」** 선택
4. GitHub 로그인/권한 허용하면 Railway 계정이 연결됨 (별도 이메일 가입 없이 GitHub로 로그인)

---

## 2단계: 새 프로젝트 만들기

1. Railway 대시보드에서 **「New Project」** 버튼 클릭
2. **「Deploy from GitHub repo」** 선택
3. GitHub 저장소 목록이 나오면 **「nvmymind/newspaper」** (또는 올려둔 저장소 이름) 선택
4. **「One-time setup」** 또는 **「Deploy now」** 같은 버튼이 있으면 클릭  
   → 저장소가 연결되고 자동으로 빌드가 시작됨

---

## 3단계: Web Service로 설정 확인 (Docker)

1. 프로젝트 안에 **서비스 1개**가 생김 (이름이 `newspaper` 등으로 보일 수 있음)
2. 그 **서비스(카드)** 를 클릭해서 들어감
3. **「Settings」** 탭으로 이동
4. 아래 항목 확인 (보통 자동으로 잡혀 있음):
   - **Source**: GitHub - nvmymind/newspaper, **Branch**: main
   - **Build**: Dockerfile 사용 (Docker 감지됨)
   - **Root Directory**: 비워 둠
5. 여기서 별도로 **Build Command / Start Command** 는 수정하지 않아도 됨 (Dockerfile이 처리)

---

## 4단계: 볼륨 추가 (데이터 유지용, 권장)

수집한 사설 목록(DB)을 재배포 후에도 유지하려면 볼륨을 붙입니다.

1. 같은 서비스 **「Settings」** 탭에서 아래로 내려감
2. **「Volumes」** 섹션 찾기
3. **「+ New Volume」** 또는 **「Add Volume」** 클릭
4. **Mount Path** 에 **`/app/data`** 입력 (정확히 이 경로)
5. 저장/적용 후 **재배포( Redeploy)** 한 번 해 주면, 이후에는 DB가 이 볼륨에 저장됨

> 볼륨을 안 붙여도 앱은 동작합니다. 다만 재배포·재시작 시 SQLite DB가 초기화되어 수집한 날짜/기사가 사라집니다.

---

## 5단계: 공개 URL 받기

1. 서비스 화면에서 **「Settings」** 탭
2. **「Networking」** 또는 **「Public Networking」** 섹션 찾기
3. **「Generate Domain」** 또는 **「Add Domain」** 클릭
4. `newspaper-production-xxxx.up.railway.app` 같은 **주소가 생성**됨
5. 이 주소를 복사해서 브라우저에 붙여 넣으면 웹 서비스 접속 가능

---

## 6단계: 배포 상태 확인

1. **「Deployments」** 탭에서 최신 배포가 **「Success」** / **「Active」** 인지 확인
2. 빌드나 실행이 실패하면 **「View Logs」** 로 에러 메시지 확인
3. URL로 접속해서 **날짜 선택 → 사설 불러오기**가 되는지 한 번 눌러 보면 됨

---

## 요약 체크리스트

| 순서 | 할 일 | 비고 |
|------|--------|------|
| 1 | railway.app 접속 → Login with GitHub | 가입 완료 |
| 2 | New Project → Deploy from GitHub repo → newspaper 선택 | 프로젝트 생성 |
| 3 | 서비스 Settings에서 Source/Branch 확인 | Docker 자동 사용 |
| 4 | Settings → Volumes → Mount Path `/app/data` 추가 | DB 유지 (권장) |
| 5 | Settings → Networking → Generate Domain | 접속 URL 확인 |
| 6 | 생성된 URL로 접속해서 동작 확인 | 완료 |

---

## 접속이 안 될 때 (Application failed to respond)

Deploy 로그에는 "Application startup complete"가 보이는데 브라우저에서 "Application failed to respond"가 나오는 경우:

1. **도메인이 이 서비스에 붙어 있는지 확인**  
   - **Settings** → **Networking** → **Public Networking**  
   - **Domains** 목록에 `*.up.railway.app` 주소가 있어야 함. 없으면 **Generate Domain** 한 번 더 클릭.

2. **최신 배포가 Active인지 확인**  
   - **Deployments** 탭에서 맨 위 배포가 **Active** (초록)인지 봅니다.  
   - 다른 배포가 Active면 그 배포의 **⋯** 메뉴에서 **Redeploy** 하거나, 실패한 배포는 무시하고 성공한 배포가 자동으로 연결되도록 기다립니다.

3. **헬스 체크로 서버 응답 확인**  
   - 배포된 주소 뒤에 `/health` 를 붙여 접속해 봅니다.  
     예: `https://newspaper-production-xxxx.up.railway.app/health`  
   - `{"status":"ok"}` 가 보이면 앱은 동작 중이고, **브라우저 캐시** 또는 **다른 URL** 문제일 수 있음.  
   - `/health` 도 안 되면 **Redeploy** (Deployments → 최신 배포 → ⋯ → Redeploy) 후 1~2분 뒤 다시 시도.

4. **한 번 재배포**  
   - **Deployments** → 가장 최근 배포 카드에서 **⋯** → **Redeploy**  
   - 빌드가 끝나고 "Active"가 된 뒤, 새로 생성된 도메인(또는 기존 도메인)으로 다시 접속.

---

## 자주 하는 질문

**Q. 비용은 얼마나 나오나요?**  
- 체험 **$5 크레딧** 사용 후, 사용량만큼 과금. 소규모 트래픽이면 월 **$1 무료 크레딧**으로도 얼마간 가능하고, 그 이상이면 보통 **$5~10/월** 안팎까지 나올 수 있음.

**Q. 코드 수정 후 다시 배포하려면?**  
- GitHub에 `git push` 하면 Railway가 자동으로 감지해서 **재배포**함. 별도 버튼 누를 필요 없음.

**Q. 도메인을 내가 가진 주소로 쓰고 싶어요.**  
- Settings → Networking → **Custom Domain** 에서 본인 도메인 연결 가능 (DNS 설정 필요).

이 가이드는 **newspaper** 프로젝트 기준으로 작성되었습니다. 저장소 이름이 다르면 해당 이름으로 선택하면 됩니다.
