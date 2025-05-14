document.addEventListener('DOMContentLoaded', function() {
    // Elements for camera capture
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const imageUpload = document.getElementById('imageUpload');
    const takePhotoBtn = document.getElementById('takePhoto');
    const captureBtn = document.getElementById('captureBtn');
    const cancelCaptureBtn = document.getElementById('cancelCaptureBtn');
    const recaptureBtn = document.getElementById('recaptureBtn');
    const processImageBtn = document.getElementById('processImage');
    const cameraContainer = document.getElementById('cameraContainer');
    const canvasContainer = document.getElementById('canvasContainer');
    const fineForm = document.getElementById('fineForm');
    const plateNumberInput = document.getElementById('plate_number');
    
    // OCR result elements
    const ocrResult = document.getElementById('ocrResult');
    const ocrError = document.getElementById('ocrError');
    const detectedPlate = document.getElementById('detectedPlate');
    const detectedState = document.getElementById('detectedState');
    const useOcrResultBtn = document.getElementById('useOcrResult');
    const errorMessage = document.getElementById('errorMessage');
    
    let stream = null;
    let capturedImage = null;
    
    // Check if all required elements exist
    if (!video || !canvas || !imageUpload || !takePhotoBtn || !processImageBtn) {
        return; // Exit if we're not on the fine entry page
    }
    
    // Initialize canvas context
    const ctx = canvas ? canvas.getContext('2d') : null;
    
    // Function to start camera
    function startCamera() {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            navigator.mediaDevices.getUserMedia({ video: true })
                .then(function(mediaStream) {
                    stream = mediaStream;
                    video.srcObject = mediaStream;
                    video.play();
                    
                    // Show camera container
                    cameraContainer.classList.remove('d-none');
                    canvasContainer.classList.add('d-none');
                })
                .catch(function(error) {
                    console.error('Error accessing camera:', error);
                    alert('Unable to access camera. Please check permissions or use image upload.');
                });
        } else {
            alert('Camera access is not supported by your browser. Please use image upload.');
        }
    }
    
    // Function to stop camera
    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            stream = null;
        }
        
        cameraContainer.classList.add('d-none');
    }
    
    // Function to capture image from camera
    function captureImage() {
        if (video && canvas && ctx) {
            // Set canvas dimensions to match video
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            
            // Draw the current video frame on the canvas
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Get the image data from canvas
            capturedImage = canvas.toDataURL('image/jpeg');
            
            // Stop the camera
            stopCamera();
            
            // Show the canvas with captured image
            canvasContainer.classList.remove('d-none');
            
            // Enable process button
            processImageBtn.disabled = false;
        }
    }
    
    // Event listener for "Take Photo" button
    takePhotoBtn.addEventListener('click', function() {
        startCamera();
    });
    
    // Event listener for "Capture" button
    captureBtn.addEventListener('click', function() {
        captureImage();
    });
    
    // Event listener for "Cancel Capture" button
    cancelCaptureBtn.addEventListener('click', function() {
        stopCamera();
    });
    
    // Event listener for "Recapture" button
    recaptureBtn.addEventListener('click', function() {
        canvasContainer.classList.add('d-none');
        capturedImage = null;
        startCamera();
    });
    
    // Event listener for image upload
    imageUpload.addEventListener('change', function(e) {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            const reader = new FileReader();
            
            reader.onload = function(event) {
                capturedImage = event.target.result;
                
                // Create an image element to get dimensions
                const img = new Image();
                img.onload = function() {
                    // Set canvas dimensions to match image
                    if (canvas && ctx) {
                        canvas.width = img.width;
                        canvas.height = img.height;
                        
                        // Draw the image on the canvas
                        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                        
                        // Show canvas container
                        canvasContainer.classList.remove('d-none');
                        cameraContainer.classList.add('d-none');
                        
                        // Enable process button
                        processImageBtn.disabled = false;
                    }
                };
                img.src = capturedImage;
            };
            
            reader.readAsDataURL(file);
        }
    });
    
    // Process the image with OCR
    processImageBtn.addEventListener('click', function() {
        if (!capturedImage) {
            alert('Please capture or upload an image first.');
            return;
        }
        
        // Show loading state
        processImageBtn.disabled = true;
        processImageBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
        
        // Hide previous results/errors
        ocrResult.classList.add('d-none');
        ocrError.classList.add('d-none');
        
        // Send the image to the server for OCR processing
        fetch('/process_image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                image_data: capturedImage
            })
        })
        .then(response => response.json())
        .then(data => {
            // Reset button state
            processImageBtn.disabled = false;
            processImageBtn.innerHTML = '<i class="fas fa-cog me-2"></i>Process Image';
            
            if (data.success) {
                // Display OCR results
                detectedPlate.textContent = data.plate_number;
                detectedState.textContent = data.state;
                
                // Add state-based class to state display
                detectedState.className = '';
                if (data.state === 'Telangana') {
                    detectedState.classList.add('text-info');
                } else if (data.state === 'Andhra Pradesh') {
                    detectedState.classList.add('text-success');
                } else {
                    detectedState.classList.add('text-secondary');
                }
                
                // Show result container
                ocrResult.classList.remove('d-none');
            } else {
                // Show error message
                errorMessage.textContent = data.error || 'Failed to detect license plate. Please try again or use manual entry.';
                ocrError.classList.remove('d-none');
            }
        })
        .catch(error => {
            console.error('Error processing image:', error);
            
            // Reset button state
            processImageBtn.disabled = false;
            processImageBtn.innerHTML = '<i class="fas fa-cog me-2"></i>Process Image';
            
            // Show error message
            errorMessage.textContent = 'An error occurred while processing the image. Please try again or use manual entry.';
            ocrError.classList.remove('d-none');
        });
    });
    
    // Use OCR result in the form
    if (useOcrResultBtn) {
        useOcrResultBtn.addEventListener('click', function() {
            const plate = detectedPlate.textContent;
            
            // Switch to manual entry tab
            const manualTab = document.getElementById('manual-tab');
            if (manualTab) {
                const tab = new bootstrap.Tab(manualTab);
                tab.show();
            }
            
            // Fill the plate number input
            if (plateNumberInput) {
                plateNumberInput.value = plate;
            }
        });
    }
});
