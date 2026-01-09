// Configuration Management JavaScript

const API_BASE = window.location.origin;

let currentConfig = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupTTSpeedSlider();
    loadConfig();
    loadPrompt();
});

// Tab switching
function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabId = button.getAttribute('data-tab');
            
            // Update buttons
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // Update content
            tabContents.forEach(content => content.classList.remove('active'));
            document.getElementById(`${tabId}-tab`).classList.add('active');
        });
    });
}

// TTS Speed slider
function setupTTSpeedSlider() {
    const slider = document.getElementById('tts-speed');
    const valueDisplay = document.getElementById('tts-speed-value');
    
    if (slider && valueDisplay) {
        slider.addEventListener('input', (e) => {
            valueDisplay.textContent = e.target.value;
        });
    }
}

// Load configuration from API
async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/api/config`);
        const data = await response.json();
        
        if (data.success) {
            currentConfig = data.config;
            populateForm(data.config);
            showStatus('Configuration loaded successfully', 'success');
        } else {
            showStatus(`Error loading config: ${data.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Failed to load configuration: ${error.message}`, 'error');
        console.error('Load config error:', error);
    }
}

// Populate form with config values
function populateForm(config) {
    // Agent settings
    if (config.agent) {
        setValue('llm-provider', config.agent.llm_provider);
        setValue('llm-model', config.agent.llm_model);
        setValue('tts-voice-id', config.agent.elevenlabs_voice_id);
        setValue('tts-speed', config.agent.tts_speed);
        document.getElementById('tts-speed-value').textContent = config.agent.tts_speed;
        setValue('stt-provider', config.agent.stt_provider);
    }
    
    // Call behavior
    if (config.call_behavior) {
        setValue('initial-greeting-delay', config.call_behavior.initial_greeting_delay);
        setValue('min-endpointing-delay', config.call_behavior.min_endpointing_delay);
        setValue('max-endpointing-delay', config.call_behavior.max_endpointing_delay);
        setValue('no-response-timeout', config.call_behavior.no_response_timeout);
        setValue('initial-silence-wait', config.call_behavior.initial_silence_wait);
        setValue('max-call-duration', config.call_behavior.max_call_duration);
    }
    
    // Integrations
    if (config.integrations) {
        setValue('livekit-url', config.integrations.livekit_url);
        setValue('sip-trunk-id', config.integrations.sip_outbound_trunk_id);
        setValue('google-sheet-id', config.integrations.google_sheet_id);
        setValue('google-sheet-name', config.integrations.google_sheet_name);
        setValue('aws-bucket', config.integrations.aws_bucket_name);
        setValue('aws-region', config.integrations.aws_region);
    }
    
    // Call dispatch
    if (config.call_dispatch) {
        setValue('call-delay-seconds', config.call_dispatch.call_delay_seconds);
        setValue('max-retries', config.call_dispatch.max_retries);
        setValue('wait-for-completion', config.call_dispatch.wait_for_call_completion);
        setValue('retry-no-answer', config.call_dispatch.retry_no_answer);
    }
}

function setValue(id, value) {
    const element = document.getElementById(id);
    if (element) {
        if (element.type === 'checkbox') {
            element.checked = value;
        } else {
            element.value = value || '';
        }
    }
}

// Save configuration
async function saveConfig() {
    try {
        // Collect form values
        const config = {
            agent: {
                llm_provider: getValue('llm-provider'),
                llm_model: getValue('llm-model'),
                elevenlabs_voice_id: getValue('tts-voice-id'),
                tts_speed: parseFloat(getValue('tts-speed')),
                stt_provider: getValue('stt-provider'),
            },
            call_behavior: {
                initial_greeting_delay: parseFloat(getValue('initial-greeting-delay')),
                min_endpointing_delay: parseFloat(getValue('min-endpointing-delay')),
                max_endpointing_delay: parseFloat(getValue('max-endpointing-delay')),
                no_response_timeout: parseFloat(getValue('no-response-timeout')),
                initial_silence_wait: parseFloat(getValue('initial-silence-wait')),
                max_call_duration: parseInt(getValue('max-call-duration')),
            },
            call_dispatch: {
                call_delay_seconds: parseInt(getValue('call-delay-seconds')),
                max_retries: parseInt(getValue('max-retries')),
                wait_for_call_completion: getValue('wait-for-completion'),
                retry_no_answer: getValue('retry-no-answer'),
            },
            integrations: {
                livekit_url: getValue('livekit-url'),
                sip_outbound_trunk_id: getValue('sip-trunk-id'),
                google_sheet_id: getValue('google-sheet-id'),
                google_sheet_name: getValue('google-sheet-name'),
                aws_bucket_name: getValue('aws-bucket'),
                aws_region: getValue('aws-region'),
            }
        };
        
        // Merge with current config to preserve other fields
        const mergedConfig = deepMerge(currentConfig, config);
        
        const response = await fetch(`${API_BASE}/api/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ config: mergedConfig }),
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentConfig = mergedConfig;
            showStatus('Configuration saved successfully!', 'success');
        } else {
            showStatus(`Error saving config: ${data.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Failed to save configuration: ${error.message}`, 'error');
        console.error('Save config error:', error);
    }
}

function getValue(id) {
    const element = document.getElementById(id);
    if (!element) return '';
    if (element.type === 'checkbox') {
        return element.checked;
    }
    return element.value;
}

// Load system prompt
async function loadPrompt() {
    try {
        const response = await fetch(`${API_BASE}/api/prompt`);
        const data = await response.json();
        
        if (data.success) {
            const promptTextarea = document.getElementById('system-prompt');
            if (promptTextarea) {
                promptTextarea.value = data.prompt || '// System prompt will be loaded from agent.py default if not set in config';
            }
        }
    } catch (error) {
        console.error('Load prompt error:', error);
    }
}

// Save system prompt
async function savePrompt() {
    try {
        const promptTextarea = document.getElementById('system-prompt');
        const prompt = promptTextarea.value;
        
        const response = await fetch(`${API_BASE}/api/prompt`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ prompt }),
        });
        
        const data = await response.json();
        
        if (data.success) {
            showStatus('System prompt saved successfully!', 'success');
        } else {
            showStatus(`Error saving prompt: ${data.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Failed to save prompt: ${error.message}`, 'error');
        console.error('Save prompt error:', error);
    }
}

// Test connection
async function testConnection() {
    try {
        showStatus('Testing connection...', 'success');
        
        const response = await fetch(`${API_BASE}/api/test/connection`, {
            method: 'POST',
        });
        
        const data = await response.json();
        
        if (data.success) {
            showStatus(`✅ ${data.message}`, 'success');
        } else {
            showStatus(`❌ ${data.error}`, 'error');
        }
    } catch (error) {
        showStatus(`Failed to test connection: ${error.message}`, 'error');
        console.error('Test connection error:', error);
    }
}

// Show status message
function showStatus(message, type = 'success') {
    const statusEl = document.getElementById('status-message');
    if (statusEl) {
        statusEl.textContent = message;
        statusEl.className = `status-message ${type}`;
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            statusEl.className = 'status-message';
        }, 5000);
    }
}

// Dispatch test call
async function dispatchTestCall() {
    const phoneNumber = document.getElementById('test-phone-number').value.trim();
    const name = document.getElementById('test-name').value.trim() || 'Test Customer';
    const businessName = document.getElementById('test-business-name').value.trim();
    const statusEl = document.getElementById('test-call-status');
    
    if (!phoneNumber) {
        statusEl.className = 'test-call-status error';
        statusEl.textContent = '❌ Please enter a phone number';
        return;
    }
    
    // Show loading state
    statusEl.className = 'test-call-status info';
    statusEl.textContent = '⏳ Dispatching test call...';
    
    try {
        const response = await fetch(`${API_BASE}/api/calls/dispatch`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                phone_number: phoneNumber,
                name: name,
                business_name: businessName,
                appointment_time: ''
            }),
        });
        
        const data = await response.json();
        
        if (data.success) {
            statusEl.className = 'test-call-status success';
            statusEl.textContent = `✅ ${data.message}`;
        } else {
            statusEl.className = 'test-call-status error';
            statusEl.textContent = `❌ ${data.error || 'Failed to dispatch call'}`;
        }
    } catch (error) {
        statusEl.className = 'test-call-status error';
        statusEl.textContent = `❌ Error: ${error.message}`;
        console.error('Test call error:', error);
    }
}

// Deep merge utility
function deepMerge(target, source) {
    const output = { ...target };
    for (const key in source) {
        if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
            output[key] = deepMerge(output[key] || {}, source[key]);
        } else {
            output[key] = source[key];
        }
    }
    return output;
}
