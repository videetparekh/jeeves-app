from fastapi import FastAPI, Form, WebSocket, Body, Request, Cookie, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from dg_api import Participant
import dg_api
import oai_api
import os
from dotenv import load_dotenv
import audio_api
from pathlib import Path
from fastapi.templating import Jinja2Templates
from deepgram import PrerecordedResponse, LiveTranscriptionEvents, LiveOptions
import urllib
import dataclasses
from typing import Dict, Callable
import json
import re
import uuid
import base64
import io

app = FastAPI()

templates = Jinja2Templates(directory="/app/html")
static_dir = Path("/app/static")
js_dir = static_dir / "js"
css_dir = static_dir / "css"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

AUDIO_CACHE_DIR= Path("./artifacts/audio/")
ANALYSIS_DIR= Path("./artifacts/analysis/")
REPORTS_DIR= Path("./artifacts/reports/")

AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

dg_client = dg_api.register_client(DEEPGRAM_API_KEY)
oai_client = oai_api.register_client(OPENAI_API_KEY)
dg_response_accumulator = dg_api.StreamResponseAccumulator()

# Routes
@app.get('/')
async def index():
    return FileResponse("html/index.html")
    

@app.websocket("/record")
async def record_audio(websocket: WebSocket):
    await websocket.accept()
    dg_live = await dg_api.register_live_connection(dg_client, dg_response_accumulator)
    
    if not dg_response_accumulator.id:
        dg_response_accumulator.register_id(str(uuid.uuid4()))
    
    try:
        while True:
            data = await websocket.receive_bytes()
            await dg_live.send(data)
    except Exception as e:
        print(f'Could not process audio: {e}')
    finally:
        await dg_live.finish()
        await websocket.close()


@app.post('/stop_record')
async def stop_recording():
    audio_analysis = dg_response_accumulator.get_final_analysis()
    print(audio_analysis)
    return process_analysis(audio_analysis, dg_response_accumulator.id)

@app.post('/submit_url')
async def submit_url(url: str = Body(..., embed=True)):
    audio_file = audio_api.download_from_youtube(url, AUDIO_CACHE_DIR)
    # audio_file = Path(AUDIO_CACHE_DIR / "conan_crashes_a_zoom_meeting__conan_on_tbs.mp4")
    if audio_file.exists():
        print("Analyzing Audio...")
        
        # audio_analysis=True
        
        # if audio_analysis:
        #     with (ANALYSIS_DIR / (audio_file.stem + ".json")).open(mode="r") as json_file:
        #         audio_analysis = PrerecordedResponse.from_json(json_file.read())
        
        with audio_file.open(mode="rb") as f:
            audio_data = f.read()
        audio_analysis = dg_api.analyze_audio(dg_client, audio_data)
        with (ANALYSIS_DIR / (audio_file.stem + ".json")).open(mode="w") as json_file:
            json_file.write(audio_analysis.to_json())

        analysis = dg_api.PrerecordedResponseParser().get_final_analysis(audio_analysis)

        return process_analysis(analysis, file_name=audio_file.stem)

@app.get("/report", response_class=HTMLResponse)
def generate_report(request: Request, file_name: str = None):
    with (REPORTS_DIR / (file_name + ".json")).open(mode="r") as json_file:
        req = json.load(json_file)
    
    req["analysis"] = req["analysis"]["results"]["paragraphed_transcript"]
    req["analysis"] = re.split(r'[\n\r]+', req["analysis"])
    req.update({"request": request})
    return templates.TemplateResponse("report.html", req)

@app.post('/chat')
async def chat(message: str = Body(..., embed=True), file_name: str = Body(..., embed=True)):
    with (REPORTS_DIR / (file_name + ".json")).open(mode="r") as json_file:
        req = json.load(json_file)
    paragraph_transcript = req["analysis"]["results"]["paragraphed_transcript"]
    oai_resp = oai_api.chat(oai_client, paragraph_transcript, message)
    return {"response": oai_resp}

@app.post('/record_chat')
async def record_chat(audio_data: str = Body(..., embed=True), file_name: str = Body(..., embed=True)):
    with (REPORTS_DIR / (file_name + ".json")).open(mode="r") as json_file:
        req = json.load(json_file)
        paragraph_transcript = req["analysis"]["results"]["paragraphed_transcript"]
        
    # try:
    audio_data = audio_data.replace("data:audio/webm;base64,", "")
    audio_data = base64.b64decode(audio_data)
    audio_stream = io.BytesIO(audio_data)
    # decoded_audio = base64.b64decode(audio_data)
    user_msg_response = dg_api.analyze_audio(dg_client, audio_stream, streamed=True)
    msg = user_msg_response.results.channels[0].alternatives[0].transcript
    print(msg)
    oai_resp = oai_api.chat(oai_client, paragraph_transcript, msg)    
    # except Exception as e:
    #     print(e)
    #     oai_resp = "Sorry I couldn't understand what you said. Please try again, or type in your request."
    #     msg = "..."
        
    # print(oai_resp)
    
    return {"response": oai_resp, "user_msg": msg}


def process_analysis(analysis, file_name):

            
        print("Generating Metadata...")
        transcript = analysis["results"]["transcript"]
        participants = dg_api.get_participants(analysis)
        duration = analysis["metadata"]["duration"]
        wps = None
        wpm = None
        if duration > 60:
            wpm = dg_api.get_words_per_minute(analysis)
        else:
            wps = dg_api.get_words_per_second(analysis)
        
        # wps = dg_api.get_words_per_second(analysis)
        oai_summary = oai_api.summarize(oai_client, transcript)

        # transcript = "as you probably all heard this is thing called Zoom Zoom conferencing it's how I do my interviews it's how a lot of late night hosts talk to celebrities these days and a lot of businesses use zoom so anyway here was my idea what if I crashed a real corporate zoom meeting for a small business so you know just to get their morale up try and get the economy moving again. So we found a company, we found an insider at a company called Tibco in Palo Alto. It's a real company. They didn't know I was going to show up. I found the information on how to log in. And so I don't know where I crashed a Tibco meeting, strategy meeting, to try and liven things up, did that earlier and well, check out what happened. Good morning. Alan's still in Hawaii. What's going on buddy? Hey, dude. All the time. Hey, Molly. There he is. I asked Dan to join us today and he was gracious enough to do it. So Dan, thanks a lot, partner, for joining us. I love it. Absolutely, Mark. Look, doing my best to join as many of these, you know, our local team calls as possible. We don't know exactly how long we will be right in this challenging moment. We do know there will be a recovery. We don't know exactly what that looks like, but preparing now, like Mark said, on things like our strategic ACCOUNT ACTION PLANS THAT SUPPORT OUR CUSTOMERS' GOALS ARE THE THINGS THAT WE'LL BE ABLE TO BE READY FOR AS WE MOVE OUT OF THAT. SO, I JUST WANTED TO MAKE SURE I CAME ON TO REINFORCE THAT. WE'RE IN A GREAT PLACE TO BE ABLE TO SUPPORT AND WORK WITH OUR COMMUNITIES. I want to apologize I'm late for the meeting I'm new to the company I wanted to break in mostly because it's pretty clear that Dan has lost his way with Tibco I mean if you have to put the name of your company on a bar behind you things are getting sad. Brian here I just want to I'm disappointed. I'm disappointed in our sales performance. I'm disappointed in a lot of you across the board. This could be a great company. It would get off our asses and make it a great company. That seems to be the problem. Oh, and Alan's got his fun background. When you were busy calling up a fun background, first guy on Zoom to think of that, you could have been thinking of real solutions. Real solutions to help Tim Toe. I'm quarantined in Hawaii. I don't care. This is a real opportunity for us to take tipco into a new direction. You have ideas. I do. Would you like to hear him? Yes, sir. Bring it. I think We should offer a more streamlined process for partner on boarding who's with me anybody. Oh yeah. Yes by exposing a P. I.S. That reduce the need for custom coding make it easier for them to integrate with their environment. Can we do that. Well are we excited about Apache Kafka. Oh yeah. Thrilled about it. About is everything our customers need and we're here to deliver that. Oh my God, when they put the chip in your brain, they sunk it in deep, didn't they? What happened to you, Dan? Remember? Remember when you were a roadie in a band and you had dreams, that's what I looked to. Dan, you were great for the company early on when you were hungry, but now you're so busy putting the TIBCO name on furniture, you forgot what it is we do. I want to customize information exchanges by using APIs over the public web in place of proprietary EDI networks. Has anyone thought of that? Indeed they have. These are great ideas. Keep them coming. Keep them coming. Well, I'd like to, but Adam is busy reloading his bong. Mark, what are you doing? I'm with you Parker man. I'm like, I'm gonna hallelujah. I'm looking for something big. Oh, that's good. I thought you were having a series of small heart attacks. I hope you're okay. I didn't know what this was. I'm worried about you guys. I cannot pull this company together by myself. Do you have suggestions for me as to how I can help this company? I really want to do my part. Anybody. I was going to say you're a great morale booster so far. Really? Do you think this is helping? Making people pay attention. Yeah. Do you think you've gained anything from having me at the company? No. Absolutely. Becky, do your children think I've added anything to the company? I don't know. What do you think? E, you give it to him Jake. Jake can see right through me. Jake, no one's given me a thumbs down since my son did it 6 minutes ago guys tiptoe was a dream to me and I think it could be your dream too. Can I at least get a TIBCO sweatshirt out of this? I know, we all know you have like 50 in the trunk of your car. All right, I'm going to go bomb about 30 more businesses today. God bless all of you. You're doing the Lord's work and the Lord's work is tibco. Are you with me? Yeah. Go tibco. 1230, Jesus Christ. Remember us fondly. I will. Alan, grow up. Grow up. Thanks, brother. Goodbye. Thanks, brother. Thank you. Hey, Conan. Thank you. Well, that helped no 1. My thanks to Chibco. They are a real company and a fine company. I thank them for their indulgence and we're gonna take a little break when we come back. Bob Odenkirk is gonna be joining me and if you feel like you're in a giving mood and you want to do a little something to help, we're recommending now that you donate to Partners in Health Coronavirus Emergency Response."
        # participants = {0: Participant(id=0, sentiment=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], speaking_time=60.580002), 2: Participant(id=2, sentiment=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], speaking_time=69.88000599999998), 1: Participant(id=1, sentiment=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], speaking_time=143.22201499999994)}
        # wps = [5, 5, 2, 2, 5, 4, 4, 3, 2, 5, 2, 2, 4, 3, 3, 3, 4, 1, 1, 5, 4, 2, 2, 1, 3, 2, 4, 3, 3, 3, 3, 6, 4, 4, 4, 5, 2, 1, 2, 1, 1, 3, 3, 3, 1, 1, 4, 1, 2, 3, 5, 2, 5, 3, 2, 4, 4, 5, 5, 5, 3, 2, 5, 5, 3, 4, 3, 3, 4, 3, 2, 6, 2, 4, 4, 3, 4, 2, 2, 3, 3, 2, 5, 5, 6, 6, 5, 2, 4, 4, 3, 3, 4, 2, 1, 3, 0, 4, 1, 4, 2, 0, 3, 5, 4, 0, 0, 0, 2, 7, 5, 4, 3, 0, 2, 3, 1, 1, 2, 3, 2, 2, 6, 2, 5, 2, 4, 5, 2, 0, 5, 2, 3, 2, 0, 0, 0, 5, 3, 3, 5, 5, 4, 1, 2, 2, 2, 0, 0, 0, 0, 0, 0, 1, 1, 11, 4, 2, 2, 1, 2, 4, 5, 3, 2, 5, 2, 4, 3, 1, 2, 0, 1, 3, 4, 3, 3, 4, 4, 4, 1, 0, 3, 2, 1, 1, 2, 3, 0, 0, 3, 3, 5, 1, 6, 5, 5, 2, 0, 0, 3, 3, 0, 0, 0, 1, 3, 3, 3, 19, 3, 4, 4, 2, 4, 5, 3, 3, 3, 4, 2, 2, 1, 4, 0, 2, 2, 5, 3, 3, 5, 3, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 2, 4, 3, 2, 1, 4, 3, 7, 4, 4, 4, 3, 3, 1, 3, 3, 3, 4, 5, 5, 5, 2, 5, 5, 2, 3, 7, 2, 1, 4, 1, 1, 5, 1, 2, 0, 0, 3, 3, 4, 1, 7, 0, 0, 3, 4, 0, 4, 3, 2, 5, 4, 3, 1, 0, 1, 3, 6, 5, 5, 4, 3, 0, 6, 4, 5, 0, 0, 1, 6, 3, 2, 2, 4, 4, 3, 4, 3, 1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 2, 3, 2, 3, 3, 8, 14, 3, 2, 3, 1, 5, 6, 2, 2, 2, 2, 2, 6, 5, 3, 3, 3, 3, 1, 2, 1, 1, 1, 1, 0, 0, 0, 0]
        # oai_summary = {
        #     "summary": "During the meeting, Conan O'Brien crashes a real corporate Zoom meeting for Tibco, a small business in Palo Alto, in an attempt to boost morale and stimulate the economy. The meeting participants discuss the current challenging moment and the need to prepare for the recovery. However, tensions arise as some participants express disappointment in the company's sales performance and lack of innovation. Ideas are shared, such as offering a streamlined process for partner onboarding and using APIs over proprietary networks. Conan's presence creates mixed reactions, with some finding it entertaining and others questioning its value. The meeting ends with Conan thanking Tibco and encouraging donations to Partners in Health Coronavirus Emergency Response.",
        #     "topics": ['Crashing a corporate Zoom meeting', 'Boosting morale and stimulating the economy', 'Challenges and preparation for recovery', 'Disappointment in sales performance', 'Ideas for innovation'], 
        #     "action_items": []
        # }
        
        with (REPORTS_DIR / (file_name + ".json")).open(mode="w") as json_file:
            contents = {"analysis": analysis,
                        "transcript": transcript, 
                        "participants": {k: dataclasses.asdict(v) for k,v in participants.items()}, 
                        "wps": wps, 
                        "wpm": wpm,
                        "oai_summary": oai_summary}
            json.dump(contents, json_file)
        return RedirectResponse(url=f"report?file_name={file_name}", status_code=303)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8501)
