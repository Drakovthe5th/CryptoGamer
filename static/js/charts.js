// Initialize Chart.js with a simple wrapper
class ChartJS {
  constructor(canvas, type = 'bar', options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.type = type;
    this.options = this.getDefaultOptions();
    this.mergeOptions(options);
    this.chart = null;
  }

  getDefaultOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          padding: 10,
          titleFont: {
            size: 14
          },
          bodyFont: {
            size: 13
          },
          callbacks: {
            label: function(context) {
              return `${context.dataset.label}: ${context.parsed.y}`;
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(0, 0, 0, 0.05)'
          },
          ticks: {
            color: '#6c757d'
          }
        },
        x: {
          grid: {
            display: false
          },
          ticks: {
            color: '#6c757d'
          }
        }
      }
    };
  }

  mergeOptions(options) {
    this.options = {
      ...this.options,
      ...options
    };
  }

  render(data) {
    // Destroy previous chart instance if exists
    if (this.chart) {
      this.chart.destroy();
    }

    this.chart = new Chart(this.ctx, {
      type: this.type,
      data: data,
      options: this.options
    });

    return this.chart;
  }

  update(newData) {
    if (this.chart) {
      this.chart.data = newData;
      this.chart.update();
    }
  }

  destroy() {
    if (this.chart) {
      this.chart.destroy();
    }
  }
}

// Initialize all charts on page
function initCharts() {
  const chartElements = document.querySelectorAll('[data-chart]');
  
  chartElements.forEach(element => {
    const canvas = element.querySelector('canvas');
    if (!canvas) return;
    
    const type = element.dataset.chart || 'bar';
    const dataUrl = element.dataset.src;
    const chartId = element.id || `chart-${Math.random().toString(36).substr(2, 9)}`;
    
    // Set up loading state
    const loading = document.createElement('div');
    loading.className = 'chart-loading';
    loading.innerHTML = '<div class="spinner"></div>';
    element.appendChild(loading);
    
    // Initialize chart
    const chart = new ChartJS(canvas, type);
    
    if (dataUrl) {
      // Fetch data from API
      fetch(dataUrl)
        .then(response => response.json())
        .then(data => {
          element.removeChild(loading);
          chart.render(data);
          createLegend(element, data);
        })
        .catch(error => {
          console.error('Error loading chart data:', error);
          element.removeChild(loading);
          showChartError(element, 'Failed to load data');
        });
    } else {
      // Use inline data
      const dataScript = element.querySelector('script[type="application/json"]');
      if (dataScript) {
        try {
          const data = JSON.parse(dataScript.textContent);
          element.removeChild(loading);
          chart.render(data);
          createLegend(element, data);
        } catch (error) {
          console.error('Error parsing chart data:', error);
          element.removeChild(loading);
          showChartError(element, 'Invalid data format');
        }
      }
    }
  });
}

// Create legend for chart
function createLegend(container, data) {
  let legendContainer = container.querySelector('.chart-legend');
  
  if (!legendContainer) {
    legendContainer = document.createElement('div');
    legendContainer.className = 'chart-legend';
    container.appendChild(legendContainer);
  }
  
  legendContainer.innerHTML = '';
  
  if (data.datasets && data.datasets.length > 0) {
    data.datasets.forEach(dataset => {
      const legendItem = document.createElement('div');
      legendItem.className = 'legend-item';
      
      const colorBox = document.createElement('div');
      colorBox.className = 'legend-color';
      colorBox.style.backgroundColor = dataset.backgroundColor || '#3498db';
      
      const label = document.createElement('span');
      label.className = 'legend-label';
      label.textContent = dataset.label || 'Dataset';
      
      legendItem.appendChild(colorBox);
      legendItem.appendChild(label);
      legendContainer.appendChild(legendItem);
    });
  }
}

// Show error message
function showChartError(container, message) {
  const error = document.createElement('div');
  error.className = 'chart-error';
  error.innerHTML = `
    <svg width="24" height="24" fill="#e74c3c" viewBox="0 0 16 16">
      <path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767L8.982 1.566zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5zm.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2z"/>
    </svg>
    <p>${message}</p>
  `;
  
  container.appendChild(error);
}

// Initialize charts when DOM is loaded
document.addEventListener('DOMContentLoaded', initCharts);

// Re-init charts when window is resized (for responsiveness)
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(initCharts, 250);
});