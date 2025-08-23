class TelegramWebEvents {
    constructor() {
        this.isTelegram = !!(window.Telegram && window.Telegram.WebApp);
    }

    // Generic method to post events
    postEvent(eventType, eventData) {
        if (this.isTelegram) {
            // Use Telegram WebApp's method if available
            window.Telegram.WebApp.postEvent(eventType, eventData);
        } else {
            // Fallback for testing outside Telegram
            console.log(`Event: ${eventType}`, eventData);
            
            // Simulate event handling for development
            this.simulateEventHandling(eventType, eventData);
        }
    }

    // Payment events
    paymentFormSubmit(credentials, title) {
        this.postEvent('payment_form_submit', { credentials, title });
    }

    // Sharing events
    shareScore(score, game) {
        this.postEvent('share_score', { score, game });
    }

    shareGame(game) {
        this.postEvent('share_game', { game });
    }

    // UI events
    setupMainButton(isVisible, isActive, text, color, textColor, isProgressVisible, hasShineEffect) {
        this.postEvent('web_app_setup_main_button', {
            is_visible: isVisible,
            is_active: isActive,
            text: text,
            color: color,
            text_color: textColor,
            is_progress_visible: isProgressVisible,
            has_shine_effect: hasShineEffect
        });
    }

    openInvoice(slug) {
        this.postEvent('web_app_open_invoice', { slug });
    }

    triggerHapticFeedback(type, impactStyle, notificationType) {
        this.postEvent('web_app_trigger_haptic_feedback', {
            type: type,
            impact_style: impactStyle,
            notification_type: notificationType
        });
    }

    setupBackButton(isVisible) {
        this.postEvent('web_app_setup_back_button', { is_visible: isVisible });
    }

    setupSettingsButton(isVisible) {
        this.postEvent('web_app_setup_settings_button', { is_visible: isVisible });
    }

    // Development simulation
    simulateEventHandling(eventType, eventData) {
        // Simulate server communication for development
        fetch('/web-events/handle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: eventType,
                data: eventData
            })
        })
        .then(response => response.json())
        .then(data => {
            console.log(`Event ${eventType} simulated response:`, data);
        })
        .catch(error => {
            console.error(`Event ${eventType} simulation error:`, error);
        });
    }
}

// Create a global instance
window.TelegramWebEvents = new TelegramWebEvents();