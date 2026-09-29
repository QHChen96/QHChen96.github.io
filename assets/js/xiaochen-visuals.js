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

  function setupCaseReplay(figure) {
    const panel = figure.querySelector('[data-xc-replay-panel]');
    const buttons = [...figure.querySelectorAll('[data-xc-replay-step]')];
    if (!panel || buttons.length !== 3) return () => {};

    const snapshots = [
      {
        label: '周一 09:01 · App 首次回复',
        old: ['旧看板：App 会话没有转人工，于是被写成“机器人解决”。', '机器人只说了“正在核查”；客户的问题还没有结案证据。'],
        linked: ['穿透同案：这里只能确认“已回复”，不能确认“已解决”。', 'case 0823 仍在等待包裹调查；回复事件不能替代结案事件。'],
      },
      {
        label: '周一 18:00 · 微信再次追问',
        old: ['旧看板：微信另起一条会话，App 那次“已解决”没有回算。', '如果按渠道工单计数，客户的第二次求助会伪装成另一个新问题。'],
        linked: ['穿透同案：同一包裹再次追问，应回挂 case 0823。', '经身份和订单归属核验后，这次联系成为原问题的复联证据。'],
      },
      {
        label: '周二 10:00 · 电话升级投诉',
        old: ['旧看板：电话又成第三条记录，App 的漂亮数字仍留在报表里。', '没有跨渠道 case，投诉与首次“解决”看起来毫无关系。'],
        linked: ['穿透同案：第三次联系证明原签收争议还没有闭环。', 'App、微信、电话挂到同一个 case 后，先前那次“已解决”必须回算。'],
      },
    ];

    let activeStep = 2;
    const label = panel.querySelector('[data-xc-replay-label]');
    const head = panel.querySelector('[data-xc-replay-head]');
    const detail = panel.querySelector('[data-xc-replay-detail]');
    function render() {
      const snapshot = snapshots[activeStep];
      const view = figure.dataset.view === 'old' ? snapshot.old : snapshot.linked;
      label.textContent = snapshot.label;
      head.textContent = view[0];
      detail.textContent = view[1];
      buttons.forEach((button, index) => {
        button.setAttribute('aria-pressed', String(index === activeStep));
      });
    }

    buttons.forEach((button, index) => {
      button.disabled = false;
      button.addEventListener('click', () => {
        activeStep = index;
        render();
      });
    });
    render();
    return render;
  }

  function setupCohortLab(lab) {
    const slider = lab.querySelector('[data-xc-cohort-slider]');
    const dots = [...lab.querySelectorAll('.xc-cohort-lab__dot')];
    const dotsImage = lab.querySelector('[data-xc-cohort-dots]');
    if (!slider || dots.length !== 100 || !dotsImage) return;

    const overlapOutput = lab.querySelector('[data-xc-cohort-overlap]');
    const numeratorOutput = lab.querySelector('[data-xc-cohort-numerator]');
    const shareOutput = lab.querySelector('[data-xc-cohort-share]');
    const explanation = lab.querySelector('[data-xc-cohort-explanation]');
    function render() {
      const overlap = Math.min(20, Math.max(0, Number(slider.value)));
      const outside = 20 - overlap;
      const matureCandidates = 76 - overlap;
      const share = (matureCandidates / 80 * 100).toFixed(2).replace(/\.?0+$/, '');

      dots.forEach((dot, index) => {
        dot.classList.toggle('is-immature', index < overlap || (index >= 76 && index < 76 + outside));
      });
      overlapOutput.textContent = `${overlap} 个`;
      numeratorOutput.textContent = `76 − ${overlap} = ${matureCandidates}`;
      shareOutput.textContent = `${matureCandidates} ÷ 80 = ${share}%`;
      explanation.textContent = `另外 ${outside} 个未成熟案例落在候选之外。${share}% 只是这个假设下的成熟候选占比；待核复联、结案证据和数据水位还会继续改变最终完成数。`;
      dotsImage.setAttribute('aria-label', `一百个案例点：七十六个候选、十四个不合格、十个人工；二十个未成熟案例里有${overlap}个在候选中，成熟候选为${matureCandidates}个`);
      slider.setAttribute('aria-valuetext', `${overlap} 个未成熟案例落在候选里，成熟候选占比 ${share}%`);
      slider.style.setProperty('--xc-range-progress', `${overlap * 5}%`);
    }

    lab.classList.add('is-ready');
    slider.disabled = false;
    slider.addEventListener('input', render);
    render();
  }

  document.querySelectorAll('[data-xc-cohort-lab]').forEach(setupCohortLab);

  document.querySelectorAll('[data-xc-shader]').forEach((figure) => {
    let refresh = () => {};
    const renderReplay = setupCaseReplay(figure);
    const switcher = figure.querySelector('.xc-switch');
    if (switcher) {
      switcher.querySelectorAll('[data-xc-view]').forEach((button) => {
        button.addEventListener('click', () => {
          figure.dataset.view = button.dataset.xcView;
          switcher.querySelectorAll('[data-xc-view]').forEach((item) => {
            item.setAttribute('aria-pressed', String(item === button));
          });
          renderReplay();
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
