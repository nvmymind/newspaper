# GitHub 연결하기

로컬 Git 저장소와 첫 커밋은 이미 되어 있습니다. 아래 순서대로 하면 GitHub에 올릴 수 있습니다.

---

## 1단계: GitHub에서 새 저장소 만들기

1. **https://github.com** 에 로그인합니다.
2. 오른쪽 상단 **+** → **New repository** 를 클릭합니다.
3. 다음처럼 설정합니다.
   - **Repository name**: `newspaper` (또는 원하는 이름, 예: `editorial-scraper`)
   - **Description**: (선택) `신문 사설 모음 웹 앱`
   - **Public** 선택
   - **"Add a README file"**, **".gitignore"**, **"License"** 는 **체크하지 않습니다.** (이미 로컬에 있음)
4. **Create repository** 를 클릭합니다.
5. 생성된 페이지에 나오는 **저장소 주소**를 복사합니다.
   - HTTPS: `https://github.com/사용자이름/newspaper.git`
   - SSH: `git@github.com:사용자이름/newspaper.git`

---

## 2단계: 로컬에서 GitHub 연결 후 푸시

**PowerShell** 또는 **명령 프롬프트**를 열고, 프로젝트 폴더로 이동한 뒤 아래를 실행합니다.  
`YOUR_USERNAME` 과 `newspaper` 는 본인 GitHub 사용자 이름과 저장소 이름으로 바꾸세요.

```powershell
cd c:\newspaper

# GitHub 저장소를 원격(remote)으로 추가 (주소는 1단계에서 복사한 걸로)
git remote add origin https://github.com/YOUR_USERNAME/newspaper.git

# 기본 브랜치 이름을 main으로 (이미 main이면 무시해도 됨)
git branch -M main

# GitHub로 푸시
git push -u origin main
```

**처음 푸시할 때** GitHub 로그인 창이 뜨거나, 브라우저에서 인증을 요구할 수 있습니다.  
- HTTPS를 쓰는 경우: GitHub 사용자 이름 + **Personal Access Token(비밀번호 대신)** 으로 로그인하는 것을 권장합니다.  
  (GitHub → Settings → Developer settings → Personal access tokens 에서 생성)

---

## 3단계: 확인

브라우저에서 `https://github.com/YOUR_USERNAME/newspaper` 를 열어 보면, 코드가 올라가 있어야 합니다.

---

## 자주 쓰는 명령어

| 하려는 일         | 명령어 |
|------------------|--------|
| 변경사항 올리기   | `git add .` → `git commit -m "메시지"` → `git push` |
| 원격 주소 확인    | `git remote -v` |
| 원격 주소 변경    | `git remote set-url origin 새주소` |
