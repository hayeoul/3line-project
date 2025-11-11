import os
from flask import Flask, render_template, request
import openai
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
from dotenv import load_dotenv # 1. .env 로더 임포트

load_dotenv() # 2. .env 파일에서 환경 변수를 불러옵니다.

# --- 설정 ---
app = Flask(__name__)

# 3. 환경 변수에서 API 키 가져오기
api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    print("="*50)
    print("경고: OPENAI_API_KEY가 .env 파일에 설정되지 않았습니다.")
    print("="*50)

# 4. (중요) OpenAI 클라이언트 초기화 (새로운 v1.0 방식)
# 앞으로 openai.chat... 대신 client.chat...을 사용합니다.
client = openai.OpenAI(api_key=api_key)


# --- (공통) AI 요약 함수 ---
def summarize_text(transcript):
    """OpenAI API를 호출하여 텍스트를 요약합니다."""
    try:
        # 5. (수정) openai. -> client.
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes the provided text into three key points in Korean."},
                {"role": "user", "content": f"다음 텍스트를 한국어로 세 문단의 핵심 내용으로 요약해줘: {transcript}"}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI 요약 API 오류: {e}")
        raise Exception("AI 요약 중 오류가 발생했습니다.")

# --- (기능 1) URL 스크립트 추출 함수 ---
def get_transcript_from_url(video_id):
    """YouTube 영상 ID로 스크립트를 추출합니다."""
    try:
        transcript_list_obj = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list_obj.find_transcript(['ko'])
            print("한국어 자막을 찾았습니다.")
        except NoTranscriptFound:
            try:
                transcript = transcript_list_obj.find_transcript(['en'])
                print("영어 자막을 찾았습니다.")
            except NoTranscriptFound:
                raise NoTranscriptFound("이 영상은 요약 가능한 한국어 또는 영어 자막이 없습니다.")

        transcript_data = transcript.fetch()
        transcript_text = " ".join([item['text'] for item in transcript_data])
        return transcript_text

    except (NoTranscriptFound, TranscriptsDisabled) as e:
        print(f"자막 추출 오류 (NoTranscriptFound): {e}")
        raise Exception(f"{e}")
    except Exception as e:
        print(f"스크립트 추출 오류 (Exception): {e}")
        print("YouTube 연결 문제 또는 쿠키 문제일 수 있습니다.")
        raise Exception(f"스크립트 추출 중 알 수 없는 오류가 발생했습니다. (자막이 없거나 YouTube 연결 문제일 수 있습니다.)")


# --- (기능 2) 파일 스크립트 추출 함수 ---
def get_transcript_from_file(file_storage):
    """OpenAI Whisper API를 사용해 오디오/비디오 파일에서 텍스트를 추출합니다."""
    try:
        # 6. (수정) FileStorage 객체를 (filename, file_stream, content_type) 튜플로 전달
        #    이것이 OpenAI v1.0+ 라이브러리가 Flask 파일을 처리하는 올바른 방식입니다.
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=(file_storage.filename, file_storage.stream, file_storage.content_type),
            response_format="text"
        )
        return response
    except Exception as e:
        print(f"OpenAI 오디오 API 오류: {e}")
        raise Exception("파일 변환 중 오류가 발생했습니다. (파일 크기 25MB 제한 초과 또는 지원하지 않는 형식일 수 있습니다)")


# --- 메인 라우트 (GET 요청만 처리) ---
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# --- URL 요약 처리 라우트 ---
@app.route('/summarize_url', methods=['POST'])
def summarize_url():
    summary = None
    error = None
    try:
        youtube_url = request.form['youtube_url']
        
        video_id = None
        if "watch?v=" in youtube_url:
            video_id = youtube_url.split("watch?v=")[1].split("&")[0]
        elif "youtu.be/" in youtube_url:
            video_id = youtube_url.split("youtu.be/")[1].split("?")[0]
        else:
            raise Exception("유효하지 않은 YouTube URL 형식입니다.")
        
        transcript = get_transcript_from_url(video_id)
        summary = summarize_text(transcript)
        
    except Exception as e:
        error = str(e)
        
    return render_template('index.html', summary=summary, error=error)

# --- 파일 요약 처리 라우트 ---
@app.route('/summarize_file', methods=['POST'])
def summarize_file():
    summary = None
    error = None
    loading = True 

    try:
        if 'media_file' not in request.files:
            raise Exception("파일이 선택되지 않았습니다.")
        
        file = request.files['media_file']
        if file.filename == '':
            raise Exception("파일이 선택되지 않았습니다.")

        transcript = get_transcript_from_file(file)
        summary = summarize_text(transcript)

    except Exception as e:
        error = str(e)
    
    loading = False
    return render_template('index.html', summary=summary, error=error, loading=loading)


if __name__ == '__main__':
    # 로컬 PC에서 테스트할 때는 debug=True로 켜는 것이 좋습니다.
    # host='0.0.0.0'을 지우면 127.0.0.1 (localhost)에서만 실행됩니다.
    app.run(port=5000, debug=True)