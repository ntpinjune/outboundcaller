// Configuration Management JavaScript

const API_BASE = window.location.origin;

let currentConfig = {};

// LLM Model Definitions
const LLM_MODELS = {
    'groq': [
        { value: 'llama-3.1-8b-instant', label: 'Llama 3.1 8B Instant (Fast)' },
        { value: 'llama3-70b-8192', label: 'Llama 3 70B (High Quality)' },
        { value: 'llama3-8b-8192', label: 'Llama 3 8B' },
        { value: 'mixtral-8x7b-32768', label: 'Mixtral 8x7B' },
        { value: 'gemma-7b-it', label: 'Gemma 7B' }
    ],
    'openai': [
        { value: 'gpt-4o-mini', label: 'GPT-4o Mini (Recommended)' },
        { value: 'gpt-4o', label: 'GPT-4o (Powerful)' },
        { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
        { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' }
    ],
    'openai-realtime': [
        { value: 'gpt-4o-mini-realtime-preview-2024-12-17', label: 'GPT-4o Mini Realtime (Fast)' },
        { value: 'gpt-4o-realtime-preview-2024-12-17', label: 'GPT-4o Realtime (High Quality)' }
    ]
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupTTSpeedSlider();
    setupVoiceSettingsSliders();
    setupAgentBehaviorControls();
    setupIdleReminderToggle();
    loadConfig();

    // LLM Provider Change Listener
    const llmProviderSelect = document.getElementById('llm-provider');
    if (llmProviderSelect) {
        llmProviderSelect.addEventListener('change', () => {
            updateLLMModelOptions();
            updateUIForRealtime();
        });
    }

    loadPrompt();
    loadPiperVoices();

    // Refresh Piper button
    const refreshPiperBtn = document.getElementById('refresh-piper');
    if (refreshPiperBtn) {
        refreshPiperBtn.addEventListener('click', () => {
            loadPiperVoices();
        });
    }

    // Piper select handler
    const piperSelect = document.getElementById('piper-model-select');
    if (piperSelect) {
        piperSelect.addEventListener('change', (e) => {
            const selectedOption = e.target.options[e.target.selectedIndex];
            if (selectedOption && selectedOption.value) {
                setValue('piper-model-path', selectedOption.value);
                // Get config path from data attribute or derive it
                const configPath = selectedOption.getAttribute('data-config');
                if (configPath) {
                    setValue('piper-config-path', configPath);
                } else {
                    setValue('piper-config-path', selectedOption.value + '.json');
                }
            } else if (e.target.value === 'manual') {
                document.getElementById('piper-manual-entry').style.display = 'block';
            }
        });
    }

    // Manual input handlers
    const manualModelInput = document.getElementById('piper-model-path-manual');
    if (manualModelInput) {
        manualModelInput.addEventListener('input', (e) => {
            setValue('piper-model-path', e.target.value);
        });
    }

    const manualConfigInput = document.getElementById('piper-config-path-manual');
    if (manualConfigInput) {
        manualConfigInput.addEventListener('input', (e) => {
            setValue('piper-config-path', e.target.value);
        });
    }
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
            updateTTSpeedRange();
        });
    }

    // Piper sliders
    const piperLengthScale = document.getElementById('piper-length-scale');
    const piperLengthScaleValue = document.getElementById('piper-length-scale-value');
    if (piperLengthScale && piperLengthScaleValue) {
        piperLengthScale.addEventListener('input', (e) => {
            piperLengthScaleValue.textContent = e.target.value;
        });
    }

    const piperNoiseScale = document.getElementById('piper-noise-scale');
    const piperNoiseScaleValue = document.getElementById('piper-noise-scale-value');
    if (piperNoiseScale && piperNoiseScaleValue) {
        piperNoiseScale.addEventListener('input', (e) => {
            piperNoiseScaleValue.textContent = e.target.value;
        });
    }

    const piperNoiseWScale = document.getElementById('piper-noise-w-scale');
    const piperNoiseWScaleValue = document.getElementById('piper-noise-w-scale-value');
    if (piperNoiseWScale && piperNoiseWScaleValue) {
        piperNoiseWScale.addEventListener('input', (e) => {
            piperNoiseWScaleValue.textContent = e.target.value;
        });
    }

    const piperVolume = document.getElementById('piper-volume');
    const piperVolumeValue = document.getElementById('piper-volume-value');
    if (piperVolume && piperVolumeValue) {
        piperVolume.addEventListener('input', (e) => {
            piperVolumeValue.textContent = e.target.value;
        });
    }
}

// Voice Settings sliders
function setupVoiceSettingsSliders() {
    // Voice Speed
    const voiceSpeed = document.getElementById('voice-speed');
    const voiceSpeedValue = document.getElementById('voice-speed-value');
    if (voiceSpeed && voiceSpeedValue) {
        voiceSpeed.addEventListener('input', (e) => {
            voiceSpeedValue.value = parseFloat(e.target.value).toFixed(1) + 'x';
        });
    }

    // Voice Temperature (LLM)
    const llmTemp = document.getElementById('llm-temperature');
    const llmTempValue = document.getElementById('llm-temperature-value');
    if (llmTemp && llmTempValue) {
        llmTemp.addEventListener('input', (e) => {
            llmTempValue.value = parseFloat(e.target.value).toFixed(1);
        });
    }

    // Voice Volume
    const voiceVolume = document.getElementById('voice-volume');
    const voiceVolumeValue = document.getElementById('voice-volume-value');
    if (voiceVolume && voiceVolumeValue) {
        voiceVolume.addEventListener('input', (e) => {
            voiceVolumeValue.value = e.target.value + '%';
        });
    }

    // New Advanced Voice Settings
    const stability = document.getElementById('stability');
    const stabilityValue = document.getElementById('stability-value');
    if (stability && stabilityValue) {
        stability.addEventListener('input', (e) => {
            stabilityValue.value = parseFloat(e.target.value).toFixed(2);
        });
    }

    const similarityBoost = document.getElementById('similarity-boost');
    const similarityBoostValue = document.getElementById('similarity-boost-value');
    if (similarityBoost && similarityBoostValue) {
        similarityBoost.addEventListener('input', (e) => {
            similarityBoostValue.value = parseFloat(e.target.value).toFixed(2);
        });
    }

    const styleExaggeration = document.getElementById('style-exaggeration');
    const styleExaggerationValue = document.getElementById('style-exaggeration-value');
    if (styleExaggeration && styleExaggerationValue) {
        styleExaggeration.addEventListener('input', (e) => {
            styleExaggerationValue.value = parseFloat(e.target.value).toFixed(2);
        });
    }
}

// Agent Behavior controls
function setupAgentBehaviorControls() {
    // Interruption Sensitivity
    const interruptionSens = document.getElementById('interruption-sensitivity');
    const interruptionSensValue = document.getElementById('interruption-sensitivity-value');
    if (interruptionSens && interruptionSensValue) {
        interruptionSens.addEventListener('input', (e) => {
            interruptionSensValue.value = parseFloat(e.target.value).toFixed(2);
        });
    }

    // Agent LLM Temperature
    const agentLLMTemp = document.getElementById('agent-llm-temperature');
    const agentLLMTempValue = document.getElementById('agent-llm-temperature-value');
    if (agentLLMTemp && agentLLMTempValue) {
        agentLLMTemp.addEventListener('input', (e) => {
            agentLLMTempValue.value = parseFloat(e.target.value).toFixed(1);
        });
    }
}

// Idle reminder toggle
function setupIdleReminderToggle() {
    const idleReminderEnabled = document.getElementById('idle-reminder-enabled');
    const idleReminderSettings = document.getElementById('idle-reminder-settings');
    if (idleReminderEnabled && idleReminderSettings) {
        idleReminderEnabled.addEventListener('change', (e) => {
            idleReminderSettings.style.display = e.target.checked ? 'block' : 'none';
        });
    }
}

// Helper functions for +/- buttons
function changeMaxCallTime(delta) {
    const input = document.getElementById('max-call-time');
    if (input) {
        let value = parseInt(input.value) + delta;
        value = Math.max(1, Math.min(15, value));
        input.value = value;
    }
}

function changeIdleTime(delta) {
    const input = document.getElementById('idle-time-seconds');
    if (input) {
        let value = parseInt(input.value) + delta;
        value = Math.max(1, Math.min(20, value));
        input.value = value;
    }
}

function changeReminderFrequency(delta) {
    const input = document.getElementById('reminder-frequency');
    if (input) {
        let value = parseInt(input.value) + delta;
        value = Math.max(1, Math.min(5, value));
        input.value = value;
    }
}

// Update LLM Model Options based on Provider
function updateLLMModelOptions(selectedModel = null) {
    const providerSelect = document.getElementById('llm-provider');
    const modelSelect = document.getElementById('llm-model');

    if (!providerSelect || !modelSelect) return;

    const provider = providerSelect.value;
    const models = LLM_MODELS[provider] || [];

    // Clear existing options
    modelSelect.innerHTML = '';

    // Add new options
    models.forEach(model => {
        const option = document.createElement('option');
        option.value = model.value;
        option.textContent = model.label;
        modelSelect.appendChild(option);
    });

    // Add "Other" option if current value isn't in list (for custom models)
    if (selectedModel && !models.find(m => m.value === selectedModel)) {
        const option = document.createElement('option');
        option.value = selectedModel;
        option.textContent = `${selectedModel} (Custom)`;
        modelSelect.appendChild(option);
    }

    // Set value
    if (selectedModel) {
        modelSelect.value = selectedModel;
    } else if (models.length > 0) {
        // Default to first option (usually the recommended one)
        modelSelect.value = models[0].value;
    }
}

// Update TTS provider UI
function updateTTSProvider() {
    try {
        const provider = document.getElementById('tts-provider').value;
        // console.log(`Updating TTS Provider UI: ${provider}`);

        const groups = {
            elevenlabs: document.getElementById('elevenlabs-voice-group'),
            elevenlabsAdvanced: document.getElementById('elevenlabs-advanced-group'),
            chatterboxApi: document.getElementById('chatterbox-api-group'),
            chatterboxVoice: document.getElementById('chatterbox-voice-group'),
            piperModel: document.getElementById('piper-model-group'),
            piperConfig: document.getElementById('piper-config-group'),
            piperLengthScale: document.getElementById('piper-length-scale-group'),
            piperNoiseScale: document.getElementById('piper-noise-scale-group'),
            piperNoiseWScale: document.getElementById('piper-noise-w-scale-group'),
            piperVolume: document.getElementById('piper-volume-group'),
            piperUseCuda: document.getElementById('piper-use-cuda-group'),
            openaiVoice: document.getElementById('openai-voice-group'),
            cartesiaVoice: document.getElementById('cartesia-voice-group'),
        };

        const speedSlider = document.getElementById('tts-speed');

        // Helper to hide everything
        Object.values(groups).forEach(el => {
            if (el) el.style.display = 'none';
        });

        // Show specific based on provider
        if (provider === 'elevenlabs') {
            if (groups.elevenlabs) groups.elevenlabs.style.display = 'flex';
            if (groups.elevenlabsAdvanced) groups.elevenlabsAdvanced.style.display = 'contents';
            if (speedSlider) { speedSlider.min = '0.7'; speedSlider.max = '1.2'; }
        } else if (provider === 'chatterbox') {
            if (groups.chatterboxApi) groups.chatterboxApi.style.display = 'flex';
            if (groups.chatterboxVoice) groups.chatterboxVoice.style.display = 'flex';
            if (speedSlider) { speedSlider.min = '0.5'; speedSlider.max = '2.0'; }
        } else if (provider === 'piper') {
            if (groups.piperModel) groups.piperModel.style.display = 'flex';
            if (groups.piperConfig) groups.piperConfig.style.display = 'flex';
            if (groups.piperUseCuda) groups.piperUseCuda.style.display = 'flex';
            if (groups.piperLengthScale) groups.piperLengthScale.style.display = 'flex';
            if (groups.piperNoiseScale) groups.piperNoiseScale.style.display = 'flex';
            if (groups.piperNoiseWScale) groups.piperNoiseWScale.style.display = 'flex';
            if (groups.piperVolume) groups.piperVolume.style.display = 'flex';
            if (speedSlider) { speedSlider.min = '0.5'; speedSlider.max = '2.0'; }
        } else if (provider === 'openai') {
            if (groups.openaiVoice) groups.openaiVoice.style.display = 'flex';
            if (speedSlider) { speedSlider.min = '0.5'; speedSlider.max = '2.0'; }
        } else if (provider === 'cartesia') {
            if (groups.cartesiaVoice) groups.cartesiaVoice.style.display = 'block';
            if (speedSlider) { speedSlider.min = '0.5'; speedSlider.max = '2.0'; }
        }

        updateTTSpeedRange();

    } catch (e) {
        console.error("Error updating TTS Provider UI:", e);
    }
}

// Update UI visibility for OpenAI Realtime
function updateUIForRealtime() {
    const llmProvider = document.getElementById('llm-provider').value;
    const isRealtime = llmProvider === 'openai-realtime';

    const ttsGroup = document.getElementById('tts-provider').closest('.form-group');
    const sttGroup = document.getElementById('stt-provider') ? document.getElementById('stt-provider').closest('.form-group') : null;
    const voiceSettingsTab = document.querySelector('.tab-button[data-tab="voice"]');

    if (isRealtime) {
        if (ttsGroup) ttsGroup.style.display = 'none';
        if (sttGroup) sttGroup.style.display = 'none';
        // Realtime doesn't use standard voice settings tab logic usually, 
        // but we might want to show OpenAI Voice options still.
        // For now, let's keep it simple and just hide the providers.

        // Show OpenAI Voice selector if hidden
        // Realtime uses a specific set of voices (alloy, echo, shimmer)
        const groups = {
            openaiVoice: document.getElementById('openai-voice-group'),
            elevenlabs: document.getElementById('elevenlabs-voice-group'),
            other: document.getElementById('elevenlabs-advanced-group')
        };

        // Hide others
        if (groups.elevenlabs) groups.elevenlabs.style.display = 'none';
        if (groups.other) groups.other.style.display = 'none';

        // Show OpenAI voice selection
        if (groups.openaiVoice) groups.openaiVoice.style.display = 'flex';

    } else {
        if (ttsGroup) ttsGroup.style.display = 'block';
        if (sttGroup) sttGroup.style.display = 'block';
        updateTTSProvider(); // Restore normal TTS UI logic
    }
}

// Update TTS speed range text
function updateTTSpeedRange() {
    const provider = document.getElementById('tts-provider').value;
    const rangeText = document.getElementById('tts-speed-range');
    if (rangeText) {
        if (provider === 'elevenlabs') {
            rangeText.textContent = 'Range: 0.7-1.2 (ElevenLabs)';
        } else if (provider === 'chatterbox') {
            rangeText.textContent = 'Range: 0.5-2.0 (Chatterbox)';
        } else if (provider === 'piper') {
            rangeText.textContent = 'Range: 0.5-2.0 (Piper - affects length_scale)';
        } else {
            rangeText.textContent = 'Range: 0.5-2.0';
        }
    }
}

// Load configuration from API
async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/api/config?t=${Date.now()}`);
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
        updateLLMModelOptions(config.agent.llm_model); // Update models and set value
        setValue('agent-location', config.agent.location || 'San Jose');

        setValue('tts-provider', config.agent.tts_provider || 'elevenlabs');
        setValue('elevenlabs-api-key', config.agent.elevenlabs_api_key || '');
        setValue('elevenlabs-voice-id', config.agent.elevenlabs_voice_id);
        setValue('cartesia-api-key', config.agent.cartesia_api_key || '');
        setValue('cartesia-voice-id', config.agent.cartesia_voice_id);
        setValue('cartesia-speed', config.agent.cartesia_speed || '1.0');
        const emotions = config.agent.cartesia_emotion || [];
        setValue('cartesia-emotion', Array.isArray(emotions) ? emotions.join(', ') : emotions);
        setValue('chatterbox-api-url', config.agent.chatterbox_api_url || 'http://localhost:8004');
        setValue('chatterbox-voice', config.agent.chatterbox_voice || 'Emily.wav');
        setValue('piper-model-path', config.agent.piper_model_path || 'piper1-gpl/en_US-lessac-medium.onnx');
        setValue('chatterbox-voice', config.agent.chatterbox_voice || 'Emily.wav');
        setValue('openai-voice', config.agent.openai_voice || 'alloy');
        setValue('piper-model-path', config.agent.piper_model_path || 'piper1-gpl/en_US-lessac-medium.onnx');
        setValue('piper-config-path', config.agent.piper_config_path || 'piper1-gpl/en_US-lessac-medium.onnx.json');

        // Update select if possible
        const piperSelect = document.getElementById('piper-model-select');
        if (piperSelect && config.agent.piper_model_path) {
            // Check if option exists
            let found = false;
            for (let i = 0; i < piperSelect.options.length; i++) {
                // Check if path matches (handling relative/absolute differences roughly)
                if (piperSelect.options[i].value.includes(config.agent.piper_model_path) ||
                    config.agent.piper_model_path.includes(piperSelect.options[i].value)) {
                    piperSelect.selectedIndex = i;
                    found = true;
                    break;
                }
            }
            if (!found) {
                // If not found in list, might be custom or manual
                // But we don't switch to manual entry view by default to keep UI clean
                // unless it's explicitly requested
                if (document.getElementById('piper-model-path-manual')) {
                    document.getElementById('piper-model-path-manual').value = config.agent.piper_model_path;
                }
                if (document.getElementById('piper-config-path-manual')) {
                    document.getElementById('piper-config-path-manual').value = config.agent.piper_config_path;
                }
            }
        }

        setCheckbox('piper-use-cuda', config.agent.piper_use_cuda || false);
        setValue('piper-length-scale', config.agent.piper_length_scale || 1.0);
        setValue('piper-noise-scale', config.agent.piper_noise_scale || 0.667);
        setValue('piper-noise-w-scale', config.agent.piper_noise_w_scale || 0.8);
        setValue('piper-volume', config.agent.piper_volume || 1.0);
        setValue('tts-speed', config.agent.tts_speed);
        document.getElementById('tts-speed-value').textContent = config.agent.tts_speed;
        if (config.agent.piper_length_scale) {
            document.getElementById('piper-length-scale-value').textContent = config.agent.piper_length_scale;
        }
        if (config.agent.piper_noise_scale) {
            document.getElementById('piper-noise-scale-value').textContent = config.agent.piper_noise_scale;
        }
        if (config.agent.piper_noise_w_scale) {
            document.getElementById('piper-noise-w-scale-value').textContent = config.agent.piper_noise_w_scale;
        }
        if (config.agent.piper_volume) {
            document.getElementById('piper-volume-value').textContent = config.agent.piper_volume;
        }
        setValue('stt-provider', config.agent.stt_provider);
        setValue('stt-provider', config.agent.stt_provider);
        updateTTSProvider(); // Update UI based on provider
        updateUIForRealtime(); // Check if we need to hide things for Realtime

        // Voice Settings
        setValue('voice-speed', config.agent.voice_speed || config.agent.tts_speed || 1.0);
        setValue('voice-volume', Math.round((config.agent.voice_volume || config.agent.piper_volume || 1.0) * 100));
        setValue('llm-temperature', config.agent.llm_temperature || 1.0);
        setValue('background-sound', config.agent.background_sound || '');

        // Noise Cancellation Mode
        const noiseCancelMode = config.agent.noise_cancellation_mode || 'bvc_telephony';
        const noiseCancelRadios = document.querySelectorAll('input[name="noise-cancellation"]');
        noiseCancelRadios.forEach(radio => {
            if (radio.value === noiseCancelMode) radio.checked = true;
        });

        // Advanced Voice Settings
        if (config.voice_settings) {
            setValue('stability', config.voice_settings.stability);
            setValue('similarity-boost', config.voice_settings.similarity_boost);
            setValue('style-exaggeration', config.voice_settings.style_exaggeration);
            setValue('optimize-streaming-latency', config.voice_settings.optimize_streaming_latency);
            setCheckbox('use-speaker-boost', config.voice_settings.use_speaker_boost);
        } else {
            // Defaults
            setValue('stability', 0.5);
            setValue('similarity-boost', 0.75);
            setValue('style-exaggeration', 0.0);
            setValue('optimize-streaming-latency', 3);
            setCheckbox('use-speaker-boost', true);
        }

        // Agent Behavior
        const responseSpeed = config.agent.response_speed || 'normal';
        const responseSpeedRadios = document.querySelectorAll('input[name="response-speed"]');
        responseSpeedRadios.forEach(radio => {
            if (radio.value === responseSpeed) radio.checked = true;
        });

        setValue('interruption-sensitivity', config.agent.interruption_sensitivity || 0.5);
        setValue('agent-llm-temperature', config.agent.llm_temperature || 1.0);
    }

    // Call behavior
    if (config.call_behavior) {
        setValue('initial-greeting-delay', config.call_behavior.initial_greeting_delay);
        setValue('min-endpointing-delay', config.call_behavior.min_endpointing_delay);
        setValue('max-endpointing-delay', config.call_behavior.max_endpointing_delay);

        // Advanced Endpointing
        setValue('punc-seconds', config.call_behavior.punc_seconds || 0.1);
        setValue('no-punc-seconds', config.call_behavior.no_punc_seconds || 1.5);
        setValue('number-seconds', config.call_behavior.number_seconds || 0.5);

        // Stop Speaking Plan
        setValue('stop-words', config.call_behavior.stop_words || 0);
        setValue('stop-voice-seconds', config.call_behavior.stop_voice_seconds || 0.2);
        setValue('backoff-seconds', config.call_behavior.backoff_seconds || 1.0);

        setValue('no-response-timeout', config.call_behavior.no_response_timeout);
        setValue('initial-silence-wait', config.call_behavior.initial_silence_wait);

        // Max Call Time (in minutes)
        const maxCallMinutes = config.call_behavior.max_call_duration ? Math.floor(config.call_behavior.max_call_duration / 60) : 5;
        setValue('max-call-time', maxCallMinutes);
        setValue('max-call-duration', config.call_behavior.max_call_duration || 300); // Keep for backwards compat

        // Idle Time & Reminders
        const idleReminderEnabled = config.call_behavior.idle_reminder_enabled !== false;
        const idleReminderCheckbox = document.getElementById('idle-reminder-enabled');
        if (idleReminderCheckbox) {
            idleReminderCheckbox.checked = idleReminderEnabled;
            const idleReminderSettings = document.getElementById('idle-reminder-settings');
            if (idleReminderSettings) {
                idleReminderSettings.style.display = idleReminderEnabled ? 'block' : 'none';
            }
        }
        setValue('idle-time-seconds', config.call_behavior.idle_time_seconds || 4);
        setValue('reminder-frequency', config.call_behavior.reminder_frequency || 1);
    }

    // Integrations
    if (config.integrations) {
        setValue('livekit-url', config.integrations.livekit_url);
        setValue('livekit-url', config.agent.livekit_url || '');
        setValue('sip-trunk-id', config.agent.sip_trunk_id || '');
        setValue('google-sheet-id', config.agent.google_sheet_id || '');
        setValue('google-sheet-name', config.integrations.google_sheet_name || 'Sheet1');
        setValue('webhook-url', config.integrations.webhook_url || '');
        if (config.integrations.webhook_secret) setValue('webhook-secret', config.integrations.webhook_secret);
        setValue('google-sheet-id', config.integrations.google_sheet_id);
        setValue('google-sheet-embed-url', config.integrations.google_sheet_embed_url);
        setValue('aws-bucket', config.integrations.aws_bucket_name);
        setValue('aws-region', config.integrations.aws_region);

        // Update embedded sheet - prioritize explicit embed URL
        updateEmbeddedSheet(config.integrations.google_sheet_embed_url || config.integrations.google_sheet_id);

        // Add live listener for sheet ID updates
        const sheetIdInput = document.getElementById('google-sheet-id');
        if (sheetIdInput) {
            sheetIdInput.oninput = (e) => {
                // Only update from ID if embed URL is empty
                const embedUrl = document.getElementById('google-sheet-embed-url').value;
                if (!embedUrl) {
                    updateEmbeddedSheet(e.target.value);
                }
            };
        }

        // Add live listener for embed URL updates
        const embedUrlInput = document.getElementById('google-sheet-embed-url');
        if (embedUrlInput) {
            embedUrlInput.oninput = (e) => {
                updateEmbeddedSheet(e.target.value || document.getElementById('google-sheet-id').value);
            };
        }
    }

    // Call dispatch
    if (config.call_dispatch) {
        setValue('call-delay-seconds', config.call_dispatch.call_delay_seconds);
        setValue('max-retries', config.call_dispatch.max_retries);
        setValue('wait-for-completion', config.call_dispatch.wait_for_call_completion);
        setValue('retry-no-answer', config.call_dispatch.retry_no_answer);
        setValue('test-phone-number', config.call_dispatch.test_phone_number);
    }
}

function getValue(id) {
    const element = document.getElementById(id);
    if (element) {
        if (element.type === 'checkbox') {
            return element.checked;
        } else if (element.type === 'radio') {
            const radios = document.querySelectorAll(`input[name="${id}"]`);
            for (let radio of radios) {
                if (radio.checked) return radio.value;
            }
            return '';
        } else {
            return element.value || '';
        }
    }
    return '';
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

function setCheckbox(id, value) {
    const element = document.getElementById(id);
    if (element && element.type === 'checkbox') {
        element.checked = !!value;
    }
}

function getCheckbox(id) {
    const element = document.getElementById(id);
    if (element && element.type === 'checkbox') {
        return element.checked;
    }
    return false;
}

// Update embedded Google Sheet
function updateEmbeddedSheet(value) {
    const iframe = document.getElementById('google-sheet-frame');
    const directLink = document.getElementById('google-sheet-link');

    if (iframe) {
        if (value && value.length > 5) {
            // Check if it's a "Published" URL (contains /d/e/)
            // OR if it contains 'pubhtml' or 'embedded=true'
            if (value.includes('/d/e/') || value.includes('pubhtml') || value.includes('<iframe')) {
                // It's likely a published Embed URL
                let src = value;

                // If user pasted full iframe tag, extract src
                if (value.includes('<iframe')) {
                    const srcMatch = value.match(/src="([^"]+)"/);
                    if (srcMatch && srcMatch[1]) {
                        src = srcMatch[1];
                    }
                }

                iframe.src = src;
                // Hide "Edit" link for published sheets as it's not the editor
                if (directLink) directLink.style.display = 'none';
                return;
            }

            // Otherwise treat as normal Sheet ID / URL
            let id = value;
            if (value.includes('/d/')) {
                const match = value.match(/\/d\/([a-zA-Z0-9-_]+)/);
                if (match && match[1]) {
                    id = match[1];
                }
            }

            // Construct preview URL
            const previewUrl = `https://docs.google.com/spreadsheets/d/${id}/preview?widget=true&headers=false`;
            const editUrl = `https://docs.google.com/spreadsheets/d/${id}/edit`;

            iframe.src = previewUrl;

            if (directLink) {
                directLink.href = editUrl;
                directLink.style.display = 'inline-block';
            }
        } else {
            iframe.src = "about:blank";
            if (directLink) directLink.style.display = 'none';
        }
    }
}

// Save configuration
async function saveConfig() {
    try {
        // Collect form values
        const config = {
            system_prompt: document.getElementById('system-prompt').value,
            agent: {
                llm_provider: getValue('llm-provider'),
                llm_model: getValue('llm-model'),
                location: getValue('agent-location'),
                tts_provider: getValue('tts-provider'),
                tts_provider: getValue('tts-provider'),
                openai_voice: getValue('openai-voice'),
                elevenlabs_api_key: getValue('elevenlabs-api-key'),
                elevenlabs_voice_id: getValue('elevenlabs-voice-id'),
                cartesia_api_key: getValue('cartesia-api-key'),
                cartesia_voice_id: getValue('cartesia-voice-id'),
                cartesia_speed: getValue('cartesia-speed'),
                cartesia_emotion: getValue('cartesia-emotion').split(',').map(e => e.trim()).filter(e => e),
                chatterbox_api_url: getValue('chatterbox-api-url'),
                chatterbox_voice: getValue('chatterbox-voice'),
                chatterbox_model: 'chatterbox-turbo', // Default model
                piper_model_path: getValue('piper-model-path'),
                piper_config_path: getValue('piper-config-path'),
                piper_use_cuda: getCheckbox('piper-use-cuda'),
                piper_length_scale: parseFloat(getValue('piper-length-scale')),
                piper_noise_scale: parseFloat(getValue('piper-noise-scale')),
                piper_noise_w_scale: parseFloat(getValue('piper-noise-w-scale')),
                piper_volume: parseFloat(getValue('piper-volume')),
                tts_speed: parseFloat(getValue('tts-speed')),
                stt_provider: getValue('stt-provider'),
                // Voice Settings
                voice_speed: parseFloat(getValue('voice-speed') || getValue('tts-speed') || 1.0),
                voice_volume: parseFloat(getValue('voice-volume') || 100) / 100, // Convert from percentage
                llm_temperature: parseFloat(getValue('llm-temperature') || getValue('agent-llm-temperature') || 1.0),
                background_sound: getValue('background-sound') || '',
                noise_cancellation_mode: document.querySelector('input[name="noise-cancellation"]:checked')?.value || 'bvc_telephony',
                // Agent Behavior
                response_speed: document.querySelector('input[name="response-speed"]:checked')?.value || 'normal',
                interruption_sensitivity: parseFloat(getValue('interruption-sensitivity') || 0.5),
            },
            voice_settings: {
                stability: parseFloat(getValue('stability')),
                similarity_boost: parseFloat(getValue('similarity-boost')),
                style_exaggeration: parseFloat(getValue('style-exaggeration')),
                optimize_streaming_latency: parseInt(getValue('optimize-streaming-latency')),
                use_speaker_boost: getCheckbox('use-speaker-boost'),
            },
            call_behavior: {
                initial_greeting_delay: parseFloat(getValue('initial-greeting-delay')),
                min_endpointing_delay: parseFloat(getValue('min-endpointing-delay')),
                max_endpointing_delay: parseFloat(getValue('max-endpointing-delay')),
                // Advanced Endpointing
                punc_seconds: parseFloat(getValue('punc-seconds')),
                no_punc_seconds: parseFloat(getValue('no-punc-seconds')),
                number_seconds: parseFloat(getValue('number-seconds')),
                // Stop Speaking Plan
                stop_words: parseInt(getValue('stop-words')),
                stop_voice_seconds: parseFloat(getValue('stop-voice-seconds')),
                backoff_seconds: parseFloat(getValue('backoff-seconds')),

                no_response_timeout: parseFloat(getValue('no-response-timeout')),
                initial_silence_wait: parseFloat(getValue('initial-silence-wait')),
                max_call_duration: parseInt(getValue('max-call-time') || 5) * 60, // Convert from minutes to seconds
                // Idle Time & Reminders
                idle_reminder_enabled: getCheckbox('idle-reminder-enabled'),
                idle_time_seconds: parseInt(getValue('idle-time-seconds') || 4),
                reminder_frequency: parseInt(getValue('reminder-frequency') || 1),
            },
            call_dispatch: {
                call_delay_seconds: parseInt(getValue('call-delay-seconds')),
                max_retries: parseInt(getValue('max-retries')),
                wait_for_call_completion: getCheckbox('wait-for-completion'),
                retry_no_answer: getCheckbox('retry-no-answer'),
                openai_realtime_voice: getValue('openai-voice'),
                test_phone_number: getValue('test-phone-number'),
            },
            integrations: {
                livekit_url: getValue('livekit-url'),
                sip_outbound_trunk_id: getValue('sip-trunk-id'),
                webhook_url: getValue('webhook-url'),
                webhook_secret: getValue('webhook-secret'),
                google_sheet_id: getValue('google-sheet-id'),
                google_sheet_embed_url: getValue('google-sheet-embed-url'),
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

// Load system prompt
async function loadPrompt() {
    try {
        const response = await fetch(`${API_BASE}/api/prompt`);
        const data = await response.json();

        if (data.success) {
            const promptTextarea = document.getElementById('system-prompt');
            if (promptTextarea) {
                // Display the actual prompt being used by the agent
                promptTextarea.value = data.prompt || '';

                // Show indicator if using default prompt
                const promptInfo = document.getElementById('prompt-info');
                if (promptInfo) {
                    if (data.is_default) {
                        promptInfo.textContent = 'Currently using default prompt from agent.py';
                        promptInfo.style.display = 'block';
                        promptInfo.style.color = '#666';
                    } else {
                        promptInfo.textContent = 'Using custom prompt from config.json';
                        promptInfo.style.display = 'block';
                        promptInfo.style.color = '#28a745';
                    }
                }
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
            if (data.reload_needed) {
                showStatus('System prompt saved successfully! ⚠️ Please restart the agent process to apply changes.', 'success');
            } else {
                showStatus('System prompt saved successfully!', 'success');
            }
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



// Load Piper Voices
async function loadPiperVoices() {
    const select = document.getElementById('piper-model-select');
    if (!select) return;

    select.innerHTML = '<option value="">Loading...</option>';

    try {
        const response = await fetch(`${API_BASE}/api/piper/voices`);
        const data = await response.json();

        select.innerHTML = '';

        if (data.success && data.voices.length > 0) {
            // Add default/detected voices
            data.voices.forEach(voice => {
                const option = document.createElement('option');
                // Use relative path for cleaner config if possible, but full path is safer
                // The backend sends full absolute paths. 
                // Let's try to make it relative to cwd if it matches
                option.value = voice.model_path;
                option.textContent = voice.name;
                option.setAttribute('data-config', voice.config_path);
                select.appendChild(option);
            });

            // Add manual entry option
            const manualOption = document.createElement('option');
            manualOption.value = "manual";
            manualOption.textContent = "-- Manual Entry --";
            select.appendChild(manualOption);

            // Re-select current value if exists
            const currentPath = getValue('piper-model-path');
            if (currentPath) {
                for (let i = 0; i < select.options.length; i++) {
                    if (select.options[i].value.includes(currentPath) || currentPath.includes(select.options[i].value)) {
                        select.selectedIndex = i;
                        break;
                    }
                }
            }
        } else {
            select.innerHTML = '<option value="">No voices found</option>';
            const manualOption = document.createElement('option');
            manualOption.value = "manual";
            manualOption.textContent = "-- Manual Entry --";
            select.appendChild(manualOption);
        }
    } catch (error) {
        console.error('Error loading Piper voices:', error);
        select.innerHTML = '<option value="">Error loading voices</option>';
    }
}

// Preview pending calls
async function previewPendingCalls() {
    const statusEl = document.getElementById('parallel-dispatch-status');
    const container = document.getElementById('preview-container');
    const tbody = document.getElementById('preview-table-body');
    const countSpan = document.getElementById('preview-count');

    // Show loading
    statusEl.className = 'test-call-status info';
    statusEl.textContent = '⏳ Fetching pending calls from Google Sheets...';
    statusEl.style.display = 'block';

    try {
        const response = await fetch(`${API_BASE}/api/calls/preview`);
        const data = await response.json();

        if (data.success) {
            statusEl.className = 'test-call-status success';
            statusEl.textContent = `✅ Found ${data.count} pending calls`;

            // Populate table
            tbody.innerHTML = '';
            if (data.calls.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="padding: 10px; text-align: center;">No pending calls found</td></tr>';
            } else {
                data.calls.forEach(call => {
                    const row = document.createElement('tr');
                    const isRetry = call.is_retry ? '<span style="color: #d9534f; font-size: 0.8em; margin-left: 5px;">(Retry)</span>' : '';
                    row.innerHTML = `
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">${call.row_number}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">${call.name || '-'}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">${call.phone_number}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">${call.status}${isRetry}</td>
                    `;
                    tbody.appendChild(row);
                });
            }

            countSpan.textContent = data.count;
            container.style.display = 'block';

            // Auto-hide status after 3s
            setTimeout(() => {
                statusEl.style.display = 'none';
            }, 3000);

        } else {
            statusEl.className = 'test-call-status error';
            statusEl.textContent = `❌ ${data.error || 'Failed to fetch calls'}`;
        }
    } catch (error) {
        statusEl.className = 'test-call-status error';
        statusEl.textContent = `❌ Error: ${error.message}`;
        console.error('Preview calls error:', error);
    }
}


// Event Source reference
let eventSource = null;

// Start parallel dispatch
async function startParallelDispatch() {
    const statusEl = document.getElementById('parallel-dispatch-status');
    const liveLogContainer = document.getElementById('live-log-container');
    const liveLog = document.getElementById('live-log');

    // Confirm first
    if (!confirm('Are you sure you want to start parallel dialing for ALL pending rows in the sheet?')) {
        return;
    }

    // Show loading state and clear logs
    statusEl.className = 'test-call-status info';
    statusEl.textContent = '🚀 Starting parallel dispatcher...';
    statusEl.style.display = 'block';

    // Clear logs for fresh run
    liveLog.textContent = ''; // Clear the live log content
    const appendLog = (message, type = 'info') => { // Define appendLog here for immediate use
        const div = document.createElement('div');
        const time = new Date().toLocaleTimeString();
        div.innerHTML = `<span style="color: #888">[${time}]</span> ${message}`;

        if (type === 'error') div.style.color = '#ff4444';
        if (type === 'success') div.style.color = '#00ff00';
        if (type === 'highlight') div.style.fontWeight = 'bold';

        liveLog.appendChild(div);
        liveLog.scrollTop = liveLog.scrollHeight;
    };
    appendLog('🚀 Initializing parallel dispatcher...', 'info');
    liveLogContainer.style.display = 'block';

    try {
        const response = await fetch(`${API_BASE}/api/calls/dispatch-parallel`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.success) {
            statusEl.className = 'test-call-status success';
            statusEl.textContent = `✅ ${data.message} (PID: ${data.pid})`;

            // Start listening for events
            setupEventSource();
        } else {
            statusEl.className = 'test-call-status error';
            statusEl.textContent = `❌ ${data.error || 'Failed to start dispatcher'}`;
        }
    } catch (error) {
        statusEl.className = 'test-call-status error';
        statusEl.textContent = `❌ Error: ${error.message}`;
        console.error('Parallel dispatch error:', error);
    }
}

function setupEventSource() {
    if (eventSource) {
        eventSource.close();
    }

    const liveLog = document.getElementById('live-log');
    eventSource = new EventSource(`${API_BASE}/api/calls/parallel/events`);

    const appendLog = (message, type = 'info') => {
        const div = document.createElement('div');
        const time = new Date().toLocaleTimeString();
        div.innerHTML = `<span style="color: #888">[${time}]</span> ${message}`;

        if (type === 'error') div.style.color = '#ff4444';
        if (type === 'success') div.style.color = '#00ff00';
        if (type === 'highlight') div.style.fontWeight = 'bold';
        if (type === 'info') div.style.color = '#17a2b8';

        liveLog.appendChild(div);

        // Auto-scroll if checkbox is checked
        const autoScroll = document.getElementById('auto-scroll-log');
        if (!autoScroll || autoScroll.checked) {
            liveLog.scrollTop = liveLog.scrollHeight;
        }
    };

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            if (data.type === 'ui_event') {
                // Handle structured UI events
                const payload = data.data;
                const eventType = data.event;

                if (eventType === 'call_starting') {
                    appendLog(`📞 Dialing ${payload.phone_number} (${payload.name}) [Row ${payload.row_number}]...`, 'highlight');
                } else if (eventType === 'call_dispatched') {
                    appendLog(`✅ Connected ${payload.phone_number} [ID: ${payload.job_id}]`, 'success');
                } else if (eventType === 'call_failed') {
                    appendLog(`❌ Failed ${payload.phone_number}: ${payload.error}`, 'error');
                } else if (eventType === 'call_completed') {
                    appendLog(`🏁 Completed ${payload.phone_number} (Status: ${payload.status})`, 'info');
                } else if (eventType === 'status_update') {
                    // Update global status text instead of logging every time
                    const statusEl = document.getElementById('parallel-dispatch-status');
                    if (statusEl) {
                        statusEl.textContent = `Active Calls: ${payload.active_calls_count} | Processed: ${payload.processed_calls}/${payload.total_calls}`;
                    }
                } else if (eventType === 'batch_started') {
                    appendLog(`📦 Starting Batch ${payload.batch_num}/${payload.total_batches} (${payload.batch_size} calls)...`, 'highlight');
                } else {
                    // Generic event
                    appendLog(JSON.stringify(payload));
                }
            } else if (data.type === 'log') {
                // Raw log message
                // Filter out boring logs if needed, but showing all for transparency is good
                appendLog(data.message, 'log');
            } else if (data.type === 'control') {
                if (data.event === 'process_ended') {
                    const rc = payload && payload.return_code !== undefined ? payload.return_code : 'unknown';
                    const exitStatus = rc === 0 ? 'success' : (rc === null ? 'aborted' : 'error');
                    appendLog(`🛑 Dispatcher process ended (Exit Code: ${rc})`, exitStatus === 'success' ? 'success' : 'highlight');
                    eventSource.close();
                    eventSource = null;

                    // Update status
                    const statusEl = document.getElementById('parallel-dispatch-status');
                    statusEl.className = 'test-call-status info';
                    statusEl.textContent = 'Process finished';
                }
            }
        } catch (e) {
            console.error('Error parsing SSE event:', e);
        }
    };

    eventSource.onerror = (err) => {
        console.error('EventSource error:', err);
        // Display error in log
        appendLog('⚠️ SSE connection interrupted. Attempting to reconnect...', 'error');

        // Browser handles basic reconnection for EventSource, but we can help it
        if (eventSource && eventSource.readyState === EventSource.CLOSED) {
            console.log('EventSource closed unexpectedly, restarting in 3s...');
            setTimeout(setupEventSource, 3000);
        }
    };
}


// Stop parallel dispatch
async function stopParallelDispatch() {
    const statusEl = document.getElementById('parallel-dispatch-status');

    // Close SSE if active
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }

    // Confirm first
    if (!confirm('Are you sure you want to STOP the dispatcher? Any scheduled calls will be cancelled.')) {
        return;
    }

    // Show loading state
    statusEl.className = 'test-call-status info';
    statusEl.textContent = '🛑 Stopping parallel dispatcher...';
    statusEl.style.display = 'block';

    try {
        const response = await fetch(`${API_BASE}/api/calls/stop-parallel`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        const data = await response.json();

        if (data.success) {
            statusEl.className = 'test-call-status success';
            statusEl.textContent = `✅ ${data.message}`;
        } else {
            statusEl.className = 'test-call-status error';
            statusEl.textContent = `❌ ${data.error || 'Failed to stop dispatcher'}`;
        }
    } catch (error) {
        statusEl.className = 'test-call-status error';
        statusEl.textContent = `❌ Error: ${error.message}`;
        console.error('Stop dispatch error:', error);
    }
}


// Start agent process (new terminal)
async function startAgentProcess() {
    const statusEl = document.getElementById('test-call-status');

    // Show loading
    statusEl.className = 'test-call-status info';
    statusEl.innerHTML = '⏳ Launching agent in new window...';
    statusEl.style.display = 'block';

    try {
        const response = await fetch(`${API_BASE}/api/agent/start`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            statusEl.className = 'test-call-status success';
            statusEl.textContent = `✅ ${data.message}`;

            // Allow user to clear message after a few seconds
            setTimeout(() => {
                statusEl.style.display = 'none';
            }, 5000);
        } else {
            statusEl.className = 'test-call-status error';
            statusEl.textContent = `❌ ${data.error || 'Failed to start agent'}`;
        }
    } catch (error) {
        statusEl.className = 'test-call-status error';
        statusEl.textContent = `❌ Error: ${error.message}`;
        console.error('Start agent error:', error);
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

// Auto-refresh Google Sheet logic
let autoRefreshInterval = null;
let countdownInterval = null;

function toggleAutoRefresh() {
    const checkbox = document.getElementById('auto-refresh-sheet');
    const statusSpan = document.getElementById('refresh-status');
    const countdownSpan = document.getElementById('refresh-countdown');

    // Save state
    localStorage.setItem('autoRefreshSheet', checkbox.checked);

    if (checkbox.checked) {
        statusSpan.style.display = 'inline';
        startAutoRefresh(countdownSpan);
    } else {
        statusSpan.style.display = 'none';
        stopAutoRefresh();
    }
}

function startAutoRefresh(countdownSpan) {
    // Clear existing to be safe
    stopAutoRefresh();

    let secondsLeft = 30;
    countdownSpan.textContent = secondsLeft;

    // Countdown timer (updates UI every second)
    countdownInterval = setInterval(() => {
        secondsLeft--;
        if (secondsLeft <= 0) {
            secondsLeft = 30;
            // Actually refresh the iframe
            refreshSheetIframe();
        }
        countdownSpan.textContent = secondsLeft;
    }, 1000);
}

function stopAutoRefresh() {
    if (countdownInterval) clearInterval(countdownInterval);
    if (autoRefreshInterval) clearInterval(autoRefreshInterval);
    countdownInterval = null;
    autoRefreshInterval = null;
}

function refreshSheetIframe() {
    const iframe = document.getElementById('google-sheet-frame');
    if (iframe && iframe.src && iframe.src !== 'about:blank') {
        console.log('Refreshing Google Sheet iframe...');
        // Reload iframe by re-assigning src (forces refresh)
        const currentSrc = iframe.src;
        iframe.src = currentSrc;
    }
}

// Initialize persistence on load
document.addEventListener('DOMContentLoaded', () => {
    const checkbox = document.getElementById('auto-refresh-sheet');
    if (checkbox) {
        const savedState = localStorage.getItem('autoRefreshSheet');
        if (savedState === 'true') {
            checkbox.checked = true;
            toggleAutoRefresh(); // Start the timer
        }
    }

    const autoScrollCheckbox = document.getElementById('auto-scroll-log');
    if (autoScrollCheckbox) {
        const savedState = localStorage.getItem('autoScrollLog');
        if (savedState === 'false') {
            autoScrollCheckbox.checked = false;
        }

        autoScrollCheckbox.addEventListener('change', (e) => {
            localStorage.setItem('autoScrollLog', e.target.checked);
        });
    }

    // Initialize prompt history
    loadPromptHistory();
});

// --- Prompt History Logic ---
const MAX_SAVED_PROMPTS = 20;
const PROMPT_HISTORY_KEY = 'agent_prompt_history';

function loadPromptHistory() {
    const select = document.getElementById('prompt-history-select');
    if (!select) return;

    const history = JSON.parse(localStorage.getItem(PROMPT_HISTORY_KEY) || '[]');

    // Clear existing options except first
    while (select.options.length > 1) {
        select.remove(1);
    }

    history.forEach((item, index) => {
        const option = document.createElement('option');
        // Truncate preview
        const preview = item.content.substring(0, 40).replace(/\n/g, ' ') + (item.content.length > 40 ? '...' : '');
        const dateStr = new Date(item.timestamp).toLocaleString();

        option.value = index;
        option.textContent = `${item.name || 'Untitled'} (${dateStr}) - ${preview}`;
        select.appendChild(option);
    });
}

function saveCurrentPromptToHistory() {
    const content = document.getElementById('system-prompt').value;
    if (!content || !content.trim()) {
        alert('Cannot save empty prompt!');
        return;
    }

    const nameInput = document.getElementById('prompt-save-name');
    const name = nameInput.value.trim();

    const history = JSON.parse(localStorage.getItem(PROMPT_HISTORY_KEY) || '[]');

    // Check for duplicate content at the top to avoid spamming
    if (history.length > 0 && history[0].content === content && history[0].name === name) {
        // Just update timestamp if exact same
        history[0].timestamp = new Date().toISOString();
    } else {
        // Add new item
        history.unshift({
            name: name,
            content: content,
            timestamp: new Date().toISOString()
        });
    }

    // Limit size
    if (history.length > MAX_SAVED_PROMPTS) {
        history.length = MAX_SAVED_PROMPTS;
    }

    localStorage.setItem(PROMPT_HISTORY_KEY, JSON.stringify(history));
    loadPromptHistory();

    // Feedback
    const btn = document.querySelector('button[onclick="saveCurrentPromptToHistory()"]');
    const originalText = btn.textContent;
    btn.textContent = 'Saved!';
    setTimeout(() => btn.textContent = originalText, 1500);
}

function loadSelectedPrompt() {
    const select = document.getElementById('prompt-history-select');
    const index = select.value;

    if (index === "") return;

    const history = JSON.parse(localStorage.getItem(PROMPT_HISTORY_KEY) || '[]');
    const item = history[index];

    if (item) {
        if (confirm('Load this saved prompt? This will replace current text.')) {
            document.getElementById('system-prompt').value = item.content;
            if (item.name) document.getElementById('prompt-save-name').value = item.name;
        }
        // Reset select to default so user can select same item again if needed (change event)
        select.value = "";
    }
}

function clearPromptHistory() {
    if (confirm('Are you sure you want to clear all saved prompts?')) {
        localStorage.removeItem(PROMPT_HISTORY_KEY);
        loadPromptHistory();
    }
}
