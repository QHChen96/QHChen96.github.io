/* Decorative shader for explanatory diagrams. All words and values remain in HTML. */
(() => {
  const vertexSource = `
    attribute vec2 a_position;
    void main() { gl_Position = vec4(a_position, 0.0, 1.0); }
  `;

  const fragmentSource = `
    precision mediump float;
    uniform vec2 u_resolution;
    uniform float u_time;
    uniform float u_focus;
    uniform vec3 u_accent;

    float hash(vec2 p) {
      return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
    }

    void main() {
      vec2 uv = gl_FragCoord.xy / u_resolution.xy;
      vec2 p = uv * vec2(u_resolution.x / u_resolution.y, 1.0);
      float t = u_time * 0.22;

      vec3 base = mix(vec3(0.019, 0.073, 0.105), vec3(0.035, 0.133, 0.149), uv.y);
      float gridX = 1.0 - smoothstep(0.0, 0.018, abs(fract(p.x * 14.0) - 0.5));
      float gridY = 1.0 - smoothstep(0.0, 0.018, abs(fract(p.y * 11.0) - 0.5));
      float grid = (gridX + gridY) * 0.028;

      float curve = 0.47 + 0.11 * sin(p.x * 2.0 + t) + 0.05 * sin(p.x * 5.0 - t * 1.3);
      float ribbon = exp(-abs(p.y - curve) * 15.0) * 0.20;
      float ribbon2 = exp(-abs(p.y - curve - 0.13) * 28.0) * 0.075;

      vec2 cell = floor(p * vec2(19.0, 12.0));
      vec2 local = fract(p * vec2(19.0, 12.0));
      float seed = hash(cell);
      vec2 star = vec2(0.2 + 0.6 * hash(cell + 2.7), 0.2 + 0.6 * hash(cell + 9.1));
      float spark = (1.0 - smoothstep(0.015, 0.052, distance(local, star)))
        * step(0.86, seed) * (0.48 + 0.52 * sin(t * 2.5 + seed * 6.28));

      float side = smoothstep(0.35, 0.85, uv.x);
      float spotlight = exp(-distance(uv, vec2(mix(0.25, 0.76, u_focus), 0.55)) * 4.2);
      vec3 warm = vec3(0.83, 0.37, 0.16);
      vec3 tint = mix(warm, u_accent, side);
      vec3 color = base + tint * (grid + ribbon + ribbon2 + spark * 0.14);
      color += mix(warm, u_accent, u_focus) * spotlight * 0.095;
      gl_FragColor = vec4(color, 1.0);
    }
  `;

  function makeShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      gl.deleteShader(shader);
      return null;
    }
    return shader;
  }

  function prepare(gl) {
    const vertex = makeShader(gl, gl.VERTEX_SHADER, vertexSource);
    const fragment = makeShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
    if (!vertex || !fragment) return null;

    const program = gl.createProgram();
    gl.attachShader(program, vertex);
    gl.attachShader(program, fragment);
    gl.linkProgram(program);
    gl.deleteShader(vertex);
    gl.deleteShader(fragment);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      gl.deleteProgram(program);
      return null;
    }

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    gl.useProgram(program);
    const position = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
    return {
      resolution: gl.getUniformLocation(program, 'u_resolution'),
      time: gl.getUniformLocation(program, 'u_time'),
      focus: gl.getUniformLocation(program, 'u_focus'),
      accent: gl.getUniformLocation(program, 'u_accent'),
    };
  }

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  document.querySelectorAll('[data-xc-shader]').forEach((figure) => {
    let refresh = () => {};
    const switcher = figure.querySelector('.xc-switch');
    if (switcher) {
      switcher.querySelectorAll('[data-xc-view]').forEach((button) => {
        button.addEventListener('click', () => {
          figure.dataset.view = button.dataset.xcView;
          switcher.querySelectorAll('[data-xc-view]').forEach((item) => {
            item.setAttribute('aria-pressed', String(item === button));
          });
          refresh();
        });
      });
      switcher.classList.add('is-ready');
    }
    const canvas = figure.querySelector('.xc-visual__canvas');
    if (!canvas) return;
    const gl = canvas.getContext('webgl', {
      alpha: false,
      antialias: false,
      depth: false,
      stencil: false,
      powerPreference: 'low-power',
    });
    if (!gl) return; // The CSS diagram is the static fallback.
    const uniforms = prepare(gl);
    if (!uniforms) return;

    const accent = figure.dataset.xcShader === 'knowledge' ? [0.29, 0.85, 0.65] : [0.29, 0.75, 0.96];
    let visible = false;
    let frame = 0;
    let lastFrame = 0;
    let lost = false;

    function resize() {
      const rect = figure.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      const width = Math.max(1, Math.round(rect.width * dpr));
      const height = Math.max(1, Math.round(rect.height * dpr));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
        gl.viewport(0, 0, width, height);
      }
    }

    function draw(time) {
      if (lost) return;
      resize();
      gl.uniform2f(uniforms.resolution, canvas.width, canvas.height);
      gl.uniform1f(uniforms.time, reducedMotion.matches ? 0 : time / 1000);
      gl.uniform1f(uniforms.focus, figure.dataset.view === 'old' ? 0 : 1);
      gl.uniform3fv(uniforms.accent, accent);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }

    function animate(time) {
      frame = 0;
      if (!visible || document.hidden || lost) return;
      if (time - lastFrame >= 32) {
        draw(time);
        lastFrame = time;
      }
      if (!reducedMotion.matches) frame = requestAnimationFrame(animate);
    }

    function update() {
      cancelAnimationFrame(frame);
      frame = 0;
      if (visible && !document.hidden && !lost) {
        draw(performance.now());
        if (!reducedMotion.matches) frame = requestAnimationFrame(animate);
      }
    }
    refresh = update;

    canvas.addEventListener('webglcontextlost', (event) => {
      event.preventDefault();
      lost = true;
      cancelAnimationFrame(frame);
      canvas.classList.remove('is-ready');
    });
    canvas.addEventListener('webglcontextrestored', () => {
      // A lost context may invalidate every GPU object. The CSS diagram remains readable.
      lost = true;
    });

    if ('ResizeObserver' in window) new ResizeObserver(update).observe(figure);
    else window.addEventListener('resize', update, { passive: true });
    document.addEventListener('visibilitychange', update);
    reducedMotion.addEventListener?.('change', update);

    if ('IntersectionObserver' in window) {
      new IntersectionObserver(([entry]) => {
        visible = entry.isIntersecting;
        update();
      }, { rootMargin: '120px' }).observe(figure);
    } else {
      visible = true;
      update();
    }
    canvas.classList.add('is-ready');

  });
})();
