from gtts import gTTS

myobj = gTTS(text="Hey! What's goin' on?", lang="en", slow=False, tld="uk")
myobj.save("output.mp3")