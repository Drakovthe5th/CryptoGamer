// Minimal Socket.IO fallback
console.log('Using Socket.IO fallback');
window.io = {
    connect: function() {
        console.warn('Socket.IO not available - using fallback');
        return {
            on: function() {},
            emit: function() {},
            disconnect: function() {}
        };
    }
};