// State Manager - Minimal implementation
console.log('State Manager loaded');

window.StateManager = window.StateManager || {
    state: {},
    listeners: [],
    
    setState: function(newState) {
        this.state = { ...this.state, ...newState };
        this.notifyListeners();
    },
    
    getState: function() {
        return this.state;
    },
    
    subscribe: function(listener) {
        this.listeners.push(listener);
        return () => {
            this.listeners = this.listeners.filter(l => l !== listener);
        };
    },
    
    notifyListeners: function() {
        this.listeners.forEach(listener => listener(this.state));
    }
};