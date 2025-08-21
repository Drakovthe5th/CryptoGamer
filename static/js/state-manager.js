// Minimal state management
window.StateManager = {
    state: {},
    setState: function(newState) {
        this.state = {...this.state, ...newState};
    },
    getState: function() {
        return this.state;
    }
};