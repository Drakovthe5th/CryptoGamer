function initCharts() {
    // User Growth Chart
    const userCtx = document.getElementById('user-growth-chart').getContext('2d');
    new Chart(userCtx, {
        type: 'line',
        data: {
            labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
            datasets: [{
                label: 'Total Users',
                data: [120, 190, 300, 500, 800, 1200],
                borderColor: '#0088cc',
                backgroundColor: 'rgba(0, 136, 204, 0.1)',
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'User Growth'
                }
            }
        }
    });

    // Rewards Distribution Chart
    const rewardsCtx = document.getElementById('rewards-distribution-chart').getContext('2d');
    new Chart(rewardsCtx, {
        type: 'doughnut',
        data: {
            labels: ['Games', 'Quests', 'Ads', 'Referrals'],
            datasets: [{
                data: [45, 25, 20, 10],
                backgroundColor: [
                    '#0088cc',
                    '#00cc88',
                    '#cc0088',
                    '#8800cc'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Rewards Distribution'
                }
            }
        }
    });

    // Withdrawals Chart
    const withdrawalsCtx = document.getElementById('withdrawals-chart').getContext('2d');
    new Chart(withdrawalsCtx, {
        type: 'bar',
        data: {
            labels: ['TON', 'Cash (OTC)', 'Other'],
            datasets: [{
                label: 'Withdrawal Amount (TON)',
                data: [850, 420, 130],
                backgroundColor: [
                    '#0088cc',
                    '#00cc88',
                    '#cc0088'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'Withdrawal Methods'
                }
            }
        }
    });

    // OTC Desk Chart
    const otcCtx = document.getElementById('otc-chart').getContext('2d');
    new Chart(otcCtx, {
        type: 'pie',
        data: {
            labels: ['USD', 'EUR', 'KES'],
            datasets: [{
                data: [65, 25, 10],
                backgroundColor: [
                    '#0088cc',
                    '#00cc88',
                    '#cc0088'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                title: {
                    display: true,
                    text: 'OTC Currency Distribution'
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', initCharts);