// Minimal Chart.js fallback
console.log('Using Chart.js fallback');
window.Chart = function() {
    console.warn('Chart.js not available - using fallback');
    return {
        destroy: function() {},
        update: function() {}
    };
};