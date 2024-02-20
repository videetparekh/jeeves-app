$(document).ready(function () {
    var ws = null;
    var isRecording = false;
    var mediaRecorder;

    $('#recordButton').click(function () {
        if (!isRecording) {
            $('.microphone-icon').removeClass('fas fa-microphone-alt inactive');
            $('.microphone-icon').addClass('fa-solid fa-microphone active');
            startRecording();
        } else {
            $('.microphone-icon').removeClass('fa-solid fa-microphone active');
            $('.microphone-icon').addClass('fas fa-microphone-alt inactive');
            stopRecording();
        }
    });

    function startRecording() {
        ws = new WebSocket('ws://localhost:8501/record');
        ws.onopen = function (event) { console.log('WebSocket connection opened'); };
        ws.onclose = function (event) { console.log('WebSocket connection closed'); };
        ws.onerror = function (error) { console.error('WebSocket error: ', error); };

        isRecording = true;
        console.log('Recording started');

        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function (stream) {
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = function (event) { 
                    if (event.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) { 
                        ws.send(event.data); 
                    } };
                mediaRecorder.start(250);
            })
            .catch(function (err) {
                console.error('Error accessing microphone: ', err);
            });
    }

    function stopRecording() {
        isRecording = false;
        if (mediaRecorder.state !== 'inactive') { 
            mediaRecorder.stop();
        }
    
        // Ensure all remaining data is sent before closing the WebSocket
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.onclose = function() {}; // Prevent redundant calls
            ws.send('');
            ws.close();
        }
        isRecording = false;
        console.log('Recording stopped');
        if (mediaRecorder.state !== 'inactive') { mediaRecorder.stop(); }

        fetch('/stop_record', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            redirect: 'follow'
        }).then(function (response) {
            if (response.redirected) {
                window.location.href = response.url;
            }
        });
    }

    $('#downloadButton').click(function () {
        var youtubeUrl = $('#youtubeUrl').val().trim();
        if (youtubeUrl !== '') {
            toggleButtonState(true);
            sendYoutubeUrl(youtubeUrl);
        } else {
            alert('Please enter a valid Youtube URL.');
        }
    });

    function toggleButtonState(isLoading) {
        if (isLoading) {
            $('#downloadButton').prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Processing');
        } else {
            $('#downloadButton').prop('disabled', false).html('Submit URL');
        }
    }

    function sendYoutubeUrl(youtubeUrl) {
        fetch('/submit_url', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ "url": youtubeUrl }),
            redirect: 'follow'
        })
            .then(function (response) {
                if (response.redirected) {
                    window.location.href = response.url;
                }
            })
            .catch(function (error) { console.error('Error submitting Youtube URL: ', error); })
            .finally(function () {
                toggleButtonState(false);
            });;
    }
});