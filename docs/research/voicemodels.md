NVIDIA just kicked off the year by pushing open source voice agents way forward.

They just dropped Nemotron Speech ASR, a speech to text model designed from the ground up for low latency use cases like real time voice agents 🔥 

The demo agent here reaches around 24ms transcription finalization, with total voice to voice latency under 500ms. That is the point where conversations start to feel natural.

What’s also interesting is the stack behind it. The agent combines three NVIDIA models working together:

→ Nemotron Speech ASR for transcription
→ Nemotron 3 Nano 30B running in 4 bit quant
→ A preview checkpoint of the upcoming Magpie text to speech model

The full voice agent is open source, and easy to deploy.

You can push it to production on Modal with Pipecat Cloud in minutes, or run it locally on an NVIDIA DGX Spark using the Docker setup from the repo.