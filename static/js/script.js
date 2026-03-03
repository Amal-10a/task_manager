// Network Animation
 const canvas = document.getElementById('networkCanvas');
if (canvas) {
    const ctx = canvas.getContext('2d');
    let particles = [];
    
    function getColors() {
        const isDark = document.body.classList.contains('dark');
        return {
            particle: isDark ? '#D2691E' : '#8B4513',
            line: isDark ? [210, 105, 30] : [139, 69, 19]
        };
    }
    
    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    
    class Particle {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.vx = (Math.random() - 0.5) * 1;
            this.vy = (Math.random() - 0.5) * 1;
            this.radius = Math.random() * 2 + 1;
        }
        
        update() {
            this.x += this.vx;
            this.y += this.vy;
            
            if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
            if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
        }
        
        draw() {
            const colors = getColors();
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = colors.particle;
            ctx.fill();
        }
    }
    
    function initParticles() {
        particles = [];
        const numParticles = Math.floor((canvas.width * canvas.height) / 15000);
        for (let i = 0; i < numParticles; i++) {
            particles.push(new Particle());
        }
    }
    
    function animate() {
        const colors = getColors();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw connections
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance < 120) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(${colors.line[0]}, ${colors.line[1]}, ${colors.line[2]}, ${0.15 * (1 - distance / 120)})`;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                }
            }
        }
        
        // Update and draw particles
        particles.forEach(particle => {
            particle.update();
            particle.draw();
        });
        
        requestAnimationFrame(animate);
    }
    
    // Initialize
    resizeCanvas();
    initParticles();
    animate();
    
    // Handle resize
    window.addEventListener('resize', () => {
        resizeCanvas();
        initParticles();
    });
}

// Theme Toggle
function toggleTheme() {
    document.body.classList.toggle('dark');
    localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
    // Update icon
    const icon = document.querySelector('.theme-toggle i');
    if (icon) {
        icon.classList.toggle('fa-moon');
        icon.classList.toggle('fa-sun');
    }
}

// Initialize theme on load
if (localStorage.getItem('theme') === 'dark' || 
    (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.body.classList.add('dark');
}

// Auto-hide alerts
setTimeout(() => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        alert.style.transition = 'opacity 0.5s ease';
        alert.style.opacity = '0';
        setTimeout(() => alert.remove(), 500);
    });
}, 5000);

// Confirm delete actions
function confirmDelete(message) {
    return confirm(message || 'هل أنت متأكد من الحذف؟');
}

// Modal functions
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

// Close modal when clicking outside
document.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal-overlay') || event.target.closest('.modal-overlay')) {
        const modals = document.querySelectorAll('[id$="Modal"]');
        modals.forEach(modal => {
            if (modal.style.display === 'flex') {
                modal.style.display = 'none';
            }
        });
    }
});

// Task status color coding
document.addEventListener('DOMContentLoaded', function() {
    const statusBadges = document.querySelectorAll('.status-badge');
    statusBadges.forEach(badge => {
        const text = badge.textContent;
        if (text.includes('معلقة')) {
            badge.classList.add('status-pending');
        } else if (text.includes('قيد التنفيذ')) {
            badge.classList.add('status-progress');
        } else if (text.includes('مكتملة')) {
            badge.classList.add('status-completed');
        }
    });
    
    // Priority color coding
    const priorityElements = document.querySelectorAll('.priority');
    priorityElements.forEach(el => {
        const text = el.textContent;
        if (text.includes('عالية')) {
            el.classList.add('priority-high');
        } else if (text.includes('متوسطة')) {
            el.classList.add('priority-medium');
        } else {
            el.classList.add('priority-normal');
        }
    });
});
