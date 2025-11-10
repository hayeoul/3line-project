import os
from flask import Flask, render_template, request, g
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
import openai

# --- 설정 [cite: 31, 32, 36] ---
app = Flask(__name__)

# 중요: 실행 전 터미널에서 API 키를 설정해야 합니다.
# export OPENAI_API_KEY='여기에_실제_API_키_입력'
openai.api_key = os.environ.get("")

if not openai.api_key:
    print("="*50)
    print("경고: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
    print("터미널에서 'export OPENAI_API_KEY=YOUR_KEY'를 실행하세요.")
    print("="*50)

# --- AI 요약 함수 [cite: 57, 58] ---
def summarize_text(transcript):
    """OpenAI API를 호출하여 텍스트를 요약합니다."""
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",  # [cite: 37]
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes the provided text into three key points in Korean."},
                {"role": "user", "content": f"다음 텍스트를 한국어로 세 문단의 핵심 내용으로 요약해줘: {transcript}"}
            ]
        )
        return response.choices[0].message.content.strip() # [cite: 42]
    except Exception as e:
        print(f"OpenAI API 오류: {e}")
        raise Exception("AI 요약 중 오류가 발생했습니다. API 키와 할당량을 확인하세요.")

# --- 스크립트 추출 함수 ---
def get_transcript(video_id):
    """YouTube 영상 ID로 스크립트를 추출합니다."""
    try:
        # 1. 사용 가능한 모든 자막 리스트를 먼저 가져옵니다.
        # (이 단계에서 'no element found' 오류가 발생할 수 있습니다)
        transcript_list_obj = YouTubeTranscriptApi.list_transcripts(video_id)

        # 2. 한국어 자막을 찾습니다.
        try:
            transcript = transcript_list_obj.find_transcript(['ko'])
            print("한국어 자막을 찾았습니다.")
        except NoTranscriptFound:
            # 2a. 한국어가 없으면 영어 자막을 찾습니다.
            try:
                transcript = transcript_list_obj.find_transcript(['en'])
                print("영어 자막을 찾았습니다.")
            except NoTranscriptFound:
                # 2b. 둘 다 없으면 에러를 발생시킵니다.
                raise NoTranscriptFound("이 영상은 요약 가능한 한국어 또는 영어 자막이 없습니다.")

        # 3. 찾은 자막의 실제 내용을 가져옵니다. (fetch)
        # (이 단계에서도 'no element found' 오류가 발생할 수 있습니다)
        transcript_data = transcript.fetch()
        
        # 4. 스크립트 텍스트를 하나로 합치기
        transcript_text = " ".join([item['text'] for item in transcript_data])
        return transcript_text

    except (NoTranscriptFound, TranscriptsDisabled) as e:
        print(f"자막 추출 오류 (NoTranscriptFound): {e}")
        raise Exception(f"{e}")
    except Exception as e:
        # 'no element found' 오류가 여기서 잡힙니다.
        print(f"스크립트 추출 오류 (Exception): {e}")
        print("YouTube 연결 문제 또는 쿠키 동의 문제일 수 있습니다.")
        raise Exception(f"스크립트 추출 중 알 수 없는 오류가 발생했습니다. (자막이 없거나 YouTube 연결 문제일 수 있습니다.)")

# --- 메인 라우트 [cite: 39, 42] ---
@app.route('/', methods=['GET', 'POST'])
def index():
    summary = None
    error = None

    if request.method == 'POST':
        youtube_url = request.form['youtube_url']
        
        try:
            # 1. URL에서 Video ID 추출
            video_id = None
            if "watch?v=" in youtube_url:
                video_id = youtube_url.split("watch?v=")[1].split("&")[0]
            elif "youtu.be/" in youtube_url:
                video_id = youtube_url.split("youtu.be/")[1].split("?")[0]
            else:
                raise Exception("유효하지 않은 YouTube URL 형식입니다.") # 

            # 2. 스크립트 추출 [cite: 40]
            transcript = get_transcript(video_id)
            
            # 3. AI 요약 요청 [cite: 41]
            summary = summarize_text(transcript)

        except Exception as e:
            error = str(e) # [cite: 49] (예외 처리)

    # 4. 결과 페이지 렌더링 
    return render_template('index.html', summary=summary, error=error)

# --- 앱 실행 ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)
