from flask import Flask, request, send_file
import subprocess
import os
import zipfile
import shutil
import sys
import uuid
import tempfile

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  #20mb 제한


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',
                                               1)[1].lower() == 'sc2replay'


@app.route("/", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        if "file" not in request.files:
            return "파일이 없습니다.", 400

        file = request.files["file"]

        if file.filename == "":
            return "파일 이름이 비어 있습니다.", 400

        if not allowed_file(file.filename):
            return ".SC2Replay 파일만 업로드 가능합니다.", 400

        # 작업 폴더 생성
        job_id = str(uuid.uuid4())
        job_dir = os.path.join(tempfile.gettempdir(), f"sc2job_{job_id}")
        os.makedirs(job_dir)

        replay_path = os.path.join(job_dir, "temp.SC2Replay")
        out_dir = os.path.join(job_dir, "out")
        zip_name = os.path.join(job_dir, "banks.zip")

        try:
            file.save(replay_path)

            # bank 재구성 실행
            result = subprocess.run(
                [sys.executable, "-m", "s2repdump.main", "--bank-rebuild", "temp.SC2Replay"],
                cwd=job_dir,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )

            print(result.stdout)
            print(result.stderr)

        except subprocess.TimeoutExpired:
            shutil.rmtree(job_dir, ignore_errors=True)
            return "리플레이 처리 시간이 초과되었습니다.", 500

        except subprocess.CalledProcessError as e:
            print("=== ERROR ===")
            print(e.stdout)
            print(e.stderr)
            shutil.rmtree(job_dir, ignore_errors=True)
            return f"에러 발생:\n{e.stderr}", 500

        # out 폴더 확인
        if not os.path.exists(out_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
            return "bank 생성 실패", 500

        # ZIP 생성
        with zipfile.ZipFile(zip_name, "w") as zipf:
            for root, dirs, files in os.walk(out_dir):
                for f in files:
                    full_path = os.path.join(root, f)
                    zipf.write(full_path, os.path.relpath(full_path, out_dir))

        response = send_file(zip_name, as_attachment=True)

        @response.call_on_close
        def cleanup():
            shutil.rmtree(job_dir, ignore_errors=True)

        return response

    return '''
    <html>
    <head>
        <meta charset="UTF-8">
        <title>SC2 리플레이 복구 도구</title>
        <style>
body {
background: linear-gradient(135deg, #1f252c, #2b3440);
color: #f1f3f5;
font-family: Arial, sans-serif;
text-align: center;
padding-top: 100px;
}

.box {
background: #2f3944;
padding: 40px;
border-radius: 15px;
width: 420px;
margin: auto;
box-shadow: 0 15px 40px rgba(0,0,0,0.45);
}

.drop-area {
margin-top: 20px;
padding: 30px;
border: 2px dashed #566575;
border-radius: 15px;
cursor: pointer;
transition: 0.3s;
background: #27313b;
color: #e6edf3;
}

.drop-area.hover {
background: #32414f;
border-color: #6cb2ff;
}

input[type=file] {
display: none;
}

input[type=submit] {
margin-top: 20px;
padding: 10px 25px;
border-radius: 20px;
border: none;
background: #5aa9ff;
color: white;
cursor: pointer;
transition: 0.2s;
}

input[type=submit]:hover {
background: #3d8be0;
}

.guide {
margin-top: 30px;
font-size: 14px;
text-align: left;
line-height: 1.6;
color: #e6edf3;
}

.small {
font-size: 12px;
color: #b8c1cc;
}
</style>
    </head>
    <body>
        <div class="box">
            <h2>SC2 리플레이 기반 저장소 복구 도구</h2>

            <form method="post" enctype="multipart/form-data" id="uploadForm">

                <div class="drop-area" id="dropArea">
                    파일을 여기에 끌어다 놓거나 클릭하여 선택하세요
                </div>

                <input type="file" name="file" id="fileInput" accept=".SC2Replay" required>
                
                <div id="fileWarning" style="color:red; font-size:13px; margin-bottom:10px; display:none;">
                    .SC2Replay 파일만 넣어야 합니다.
                </div>
                <input type="submit" value="복구 실행">
            </form>

            <div class="guide">
                <b>사용 방법</b><br><br>

                1. <b>.SC2Replay</b> 파일을 업로드합니다.<br>
                <div class="small">
                (리플레이 파일 위치 : 내 문서 → StarCraft II → 닉네임 폴더 → Replays → Multiplayer → 맵이름.SC2Replay)
                </div><br>

                2. 생성된 <b>Banks.zip</b> 파일을 다운로드합니다.<br><br>

                3. ZIP 파일의 압축을 해제합니다.<br><br>

                4. 자신의 닉네임과 동일한 <b>폴더</b>를 찾습니다.<br><br>

                5. 찾은 폴더 안의 하위 폴더를 <b>StarCraft II Bank 경로</b>에 붙여넣으면 완료됩니다.<br>
                <div class="small">
                (<strong>복사 예시 : Banks.zip → 3-S2-1-12345_닉네임 → <u>3-S2-1-23456</u> 폴더 복사</strong>)<br>
                (<strong>붙여넣기 위치 : 내 문서 → StarCraft II → 닉네임 폴더 → <u>Banks</u> 에 붙여넣기</strong>)
                </div>
            </div>
        </div>

        <script>
            const dropArea = document.getElementById("dropArea");
            const fileInput = document.getElementById("fileInput");
            const warning = document.getElementById("fileWarning");
        
            document.getElementById("uploadForm").addEventListener("submit", function(e) {
                const file = fileInput.files[0];
        
                if (!file || !file.name.toLowerCase().endsWith(".sc2replay")) {
                    e.preventDefault();
                    warning.style.display = "block";
                } else {
                    warning.style.display = "none";
                }
            });
        
            fileInput.addEventListener("change", function() {
                const file = fileInput.files[0];
        
                if (file && file.name.toLowerCase().endsWith(".sc2replay")) {
                    warning.style.display = "none";
                }
            });

            dropArea.addEventListener("click", () => fileInput.click());

            dropArea.addEventListener("dragover", (e) => {
                e.preventDefault();
                dropArea.classList.add("hover");
            });

            dropArea.addEventListener("dragleave", () => {
                dropArea.classList.remove("hover");
            });

            dropArea.addEventListener("drop", (e) => {
                e.preventDefault();
                dropArea.classList.remove("hover");

                if (e.dataTransfer.files.length) {
                    fileInput.files = e.dataTransfer.files;
                    dropArea.innerText = e.dataTransfer.files[0].name;
                }
            });

            fileInput.addEventListener("change", () => {
                if (fileInput.files.length) {
                    dropArea.innerText = fileInput.files[0].name;
                }
            });
        </script>

    </body>
    </html>
    '''
@app.route("/ping")
def ping():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
