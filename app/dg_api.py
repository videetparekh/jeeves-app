from pathlib import Path
from deepgram import DeepgramClient, PrerecordedOptions, LiveTranscriptionEvents, LiveOptions
from typing import List, Callable, Dict
import httpx
from dataclasses import dataclass, field
import json

@dataclass
class Participant:
    id: int
    sentiment: List = field(default_factory=list)
    speaking_time: float = 0.0
    
    def add_spoken(self, speech_time):
        self.speaking_time+=speech_time

@dataclass
class StreamResponseAccumulator:
    id: str = None
    response_list = []
    meta_list = []
    final_response = None
    
    def __post_init__(self):
        self.final_response = {
            "metadata": {"duration": 0.0}, 
            "results": {"transcript": "", "words": [], "paragraphed_transcript": ""}
        }
    
    def register_id(self, id):
        self.id = id
    
    def register_response(self, response):
        if response.is_final:
            self.final_response["metadata"]["duration"] += response.duration
            self.final_response["results"]["transcript"] = self.final_response["results"]["transcript"] + " " + response.channel.alternatives[0].transcript
            self.final_response["results"]["words"].extend([w.to_dict() for w in response.channel.alternatives[0].words])
            self.final_response["results"]["paragraphed_transcript"] = self.final_response["results"]["paragraphed_transcript"] + self.create_paragraph(response.channel.alternatives[0].words)
        
       # self.response_list.append(response)
       # with open(f"/app/artifacts/temp_responses/{self.id+str(len(self.response_list))}.json", "w") as f:
       #     json.dump(response.to_dict(), f)
    
    def get_final_analysis(self):
        return self.final_response
            
    def create_paragraph(self, words):
        p = ""
        last_speaker = None
        for word in words:
            if word.speaker != last_speaker:
                p += f"\n\nSpeaker {word.speaker}: "
            last_speaker = word.speaker
            p += word.punctuated_word + " "
        return p

@dataclass
class PrerecordedResponseParser:
    final_response = None
    
    def __post_init__(self):
        self.final_response = {
            "metadata": {"duration": 0.0}, 
            "results": {"transcript": "", "words": [], "paragraphed_transcript": ""}
        }
    
    def get_final_analysis(self, response):
        if response:
            channel0 = response.results.channels[0]
            
            self.final_response["metadata"]["duration"] = response.metadata.duration
            self.final_response["results"]["transcript"] = channel0.alternatives[0].transcript
            self.final_response["results"]["words"].extend([self.clean_word(w) for w in channel0.alternatives[0].words])
            self.final_response["results"]["paragraphed_transcript"] = channel0.alternatives[0].paragraphs.transcript    
        return self.final_response

    def clean_word(self, word):
        return {
            "word": word.word,
            "start": word.start,
            "end": word.end,
            "confidence": word.confidence,
            "punctuated_word": word.punctuated_word,
            "speaker": word.speaker,
            "speaker_confidence": word.speaker_confidence
        }

DG_LISTEN_OPTIONS = PrerecordedOptions(
    model="nova-2", 
    language="en", 
    smart_format=True, 
    paragraphs=True, 
    utterances=True, 
    diarize=True,
    summarize="v2",
    sentiment=False
)

DG_LIVE_OPTIONS = LiveOptions(
    model="base",
    language="en-US",
    smart_format=True,
)

timeout = httpx.Timeout(500.0)

def register_client(api_key):
    return DeepgramClient(api_key) 

async def register_live_connection(dg_client, stream_resp_acc: StreamResponseAccumulator):
    dg_connection = dg_client.listen.asynclive.v("1")

    async def on_message(self, result, **kwargs):
        stream_resp_acc.register_response(result)
        sentence = result.channel.alternatives[0].transcript
        print(sentence)

    async def on_metadata(self, metadata, **kwargs):
        pass

    async def on_speech_started(self, speech_started, **kwargs):
        print(f"\n\n{speech_started}\n\n")

    async def on_utterance_end(self, utterance_end, **kwargs):
        print(f"\n\n{utterance_end}\n\n")

    async def on_error(self, error, **kwargs):
        print(f"\n\n{error}\n\n")

    dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
    dg_connection.on(LiveTranscriptionEvents.Metadata, on_metadata)
    dg_connection.on(LiveTranscriptionEvents.SpeechStarted, on_speech_started)
    dg_connection.on(LiveTranscriptionEvents.UtteranceEnd, on_utterance_end)
    dg_connection.on(LiveTranscriptionEvents.Error, on_error)
    
    await dg_connection.start(DG_LIVE_OPTIONS)
    return dg_connection
    

# Function to analyze audio using Deepgram API
def analyze_audio(dg_client, audio_data, streamed=False):
    if streamed:
        return dg_client.listen.prerecorded.v('1').transcribe_file({"stream": audio_data}, DG_LISTEN_OPTIONS, timeout=timeout)
    else:
        return dg_client.listen.prerecorded.v('1').transcribe_file({"buffer": audio_data}, DG_LISTEN_OPTIONS, timeout=timeout)

def get_participants(response_obj):
    participants = dict()
    for word in response_obj["results"]["words"]:
        participant = word["speaker"]
        if not participant in participants:
            participants[participant] = Participant(id=participant)    
        participants[participant].add_spoken(word["end"] - word["start"])
    return participants

def get_words_per_second(response_obj):
    wps=[0]*(int(response_obj["metadata"]["duration"])+1)
    for word in response_obj["results"]["words"]:
        mid_time = int((word["end"] + word["start"])//2)
        wps[mid_time]+=1
    return wps

def get_words_per_minute(response_obj):
    duration_minutes = int(response_obj["metadata"]["duration"]/60)
    wpm = [0] * (duration_minutes + 1)
    for word in response_obj["results"]["words"]:
        mid_time = int((word["end"] + word["start"]) // 2)
        wpm[int(mid_time / 60)] += 1
    return wpm
