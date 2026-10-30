import * as THREE from "three";
import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/loaders/GLTFLoader.js";

const container = document.querySelector("#laLloronaScene");

if (container) {
  const loading = document.querySelector("#laLloronaLoading");
  const modelStatus = document.querySelector("#laLloronaModelStatus");
  const ambienceButton = document.querySelector("#toggleLloronaAmbience");
  const audioStatus = document.querySelector("#lloronaAudioStatus");
  const chatMessages = document.querySelector("#lloronaChatMessages");
  const questionForm = document.querySelector("#lloronaQuestionForm");
  const questionInput = document.querySelector("#lloronaQuestion");
  const languageSelect = document.querySelector("#lloronaLanguage");
  const chatStatus = document.querySelector("#lloronaChatStatus");
  const sendButton = document.querySelector("#sendLloronaQuestion");
  const reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  let reducedMotion = reducedMotionQuery.matches;
  let ambienceContext = null;
  let ambienceMaster = null;
  let ambienceAnalyser = null;
  let ambienceTimer = null;
  let ambienceNodes = [];
  let ambienceStarting = false;
  let animationFrame = null;
  let lastRenderedAt = 0;
  let characterMixer = null;
  let characterModel = null;
  let activeAnimationName = null;
  const characterClock = new THREE.Clock();
  const conversationHistory = [];
  let chatBusy = false;

  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    powerPreference: "low-power",
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.02;
  container.prepend(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x061014);
  scene.fog = new THREE.FogExp2(0x0b1b1d, 0.019);

  const camera = new THREE.PerspectiveCamera(
    48,
    container.clientWidth / container.clientHeight,
    0.1,
    120,
  );
  camera.position.set(0, 3.2, 12.5);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = !reducedMotion;
  controls.enablePan = false;
  controls.enableZoom = true;
  controls.minDistance = 8.5;
  controls.maxDistance = 16;
  controls.minPolarAngle = Math.PI * 0.29;
  controls.maxPolarAngle = Math.PI * 0.48;
  controls.minAzimuthAngle = -0.42;
  controls.maxAzimuthAngle = 0.42;
  controls.target.set(0, 1.25, -7);

  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(72, 24, 14),
    new THREE.MeshBasicMaterial({ color: 0x08171d, side: THREE.BackSide }),
  );
  scene.add(sky);

  scene.add(new THREE.HemisphereLight(0x8fb3bc, 0x10201c, 1.25));

  const moonLight = new THREE.DirectionalLight(0xcde3e4, 2.8);
  moonLight.position.set(10, 14, -12);
  scene.add(moonLight);

  const moon = new THREE.Mesh(
    new THREE.CircleGeometry(1.35, 32),
    new THREE.MeshBasicMaterial({ color: 0xdcebec, fog: false }),
  );
  moon.position.set(10, 13, -28);
  moon.lookAt(camera.position);
  scene.add(moon);

  const moonHalo = new THREE.Mesh(
    new THREE.CircleGeometry(2.3, 32),
    new THREE.MeshBasicMaterial({
      color: 0xabc8cc,
      transparent: true,
      opacity: 0.09,
      depthWrite: false,
      fog: false,
    }),
  );
  moonHalo.position.copy(moon.position);
  moonHalo.position.z += 0.06;
  moonHalo.lookAt(camera.position);
  scene.add(moonHalo);

  const bankMaterial = new THREE.MeshStandardMaterial({
    color: 0x172a25,
    roughness: 1,
  });
  const createBank = (x) => {
    const bank = new THREE.Mesh(new THREE.BoxGeometry(16, 0.75, 58), bankMaterial);
    bank.position.set(x, -0.44, -12);
    scene.add(bank);
  };
  createBank(-12.5);
  createBank(12.5);

  const waterUniforms = {
    time: { value: 0 },
    moonDirection: { value: new THREE.Vector2(0.68, 0.32) },
  };
  const water = new THREE.Mesh(
    new THREE.PlaneGeometry(10.5, 58, 28, 80),
    new THREE.ShaderMaterial({
      uniforms: waterUniforms,
      transparent: true,
      vertexShader: `
        uniform float time;
        varying vec2 vUv;
        varying float vWave;

        void main() {
          vUv = uv;
          vec3 transformed = position;
          float wave = sin(position.y * 0.72 + time * 0.48) * 0.055;
          wave += sin(position.x * 2.1 - time * 0.35) * 0.025;
          transformed.z += wave;
          vWave = wave;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(transformed, 1.0);
        }
      `,
      fragmentShader: `
        uniform vec2 moonDirection;
        varying vec2 vUv;
        varying float vWave;

        void main() {
          vec3 deepWater = vec3(0.025, 0.12, 0.15);
          vec3 nearWater = vec3(0.07, 0.22, 0.24);
          float depthMix = smoothstep(0.0, 1.0, vUv.y);
          float streak = 1.0 - smoothstep(0.02, 0.18, abs(vUv.x - moonDirection.x));
          streak *= smoothstep(0.2, 0.95, vUv.y);
          streak *= 0.55 + abs(vWave) * 5.0;
          vec3 color = mix(nearWater, deepWater, depthMix);
          color += vec3(0.43, 0.61, 0.62) * streak * 0.42;
          gl_FragColor = vec4(color, 0.94);
        }
      `,
    }),
  );
  water.rotation.x = -Math.PI / 2;
  water.position.set(0, -0.03, -12);
  scene.add(water);

  const reflectionMaterial = new THREE.MeshBasicMaterial({
    color: 0xb8d6d6,
    transparent: true,
    opacity: 0.1,
    depthWrite: false,
  });
  for (let index = 0; index < 8; index += 1) {
    const reflection = new THREE.Mesh(
      new THREE.PlaneGeometry(1.6 + index * 0.18, 0.06 + index * 0.025),
      reflectionMaterial.clone(),
    );
    reflection.rotation.x = -Math.PI / 2;
    reflection.position.set(1.7, 0.015, -10 - index * 1.7);
    reflection.material.opacity = 0.12 - index * 0.008;
    scene.add(reflection);
  }

  const reedGeometry = new THREE.CylinderGeometry(0.025, 0.045, 1.35, 5);
  const reedMaterial = new THREE.MeshStandardMaterial({
    color: 0x29483a,
    roughness: 1,
  });
  const reeds = new THREE.InstancedMesh(reedGeometry, reedMaterial, 170);
  const reedMatrix = new THREE.Matrix4();
  const reedRotation = new THREE.Quaternion();
  const reedScale = new THREE.Vector3();
  for (let index = 0; index < reeds.count; index += 1) {
    const side = index % 2 === 0 ? -1 : 1;
    const x = side * (5.5 + Math.random() * 3.1);
    const z = 10 - Math.random() * 47;
    const height = 0.65 + Math.random() * 0.85;
    reedRotation.setFromEuler(
      new THREE.Euler((Math.random() - 0.5) * 0.08, Math.random() * Math.PI, 0),
    );
    reedScale.set(1, height, 1);
    reedMatrix.compose(
      new THREE.Vector3(x, height * 0.66 - 0.05, z),
      reedRotation,
      reedScale,
    );
    reeds.setMatrixAt(index, reedMatrix);
  }
  scene.add(reeds);

  const shrubGeometry = new THREE.IcosahedronGeometry(0.6, 0);
  const shrubMaterial = new THREE.MeshStandardMaterial({
    color: 0x1c352c,
    roughness: 1,
  });
  const shrubs = new THREE.InstancedMesh(shrubGeometry, shrubMaterial, 32);
  for (let index = 0; index < shrubs.count; index += 1) {
    const side = index % 2 === 0 ? -1 : 1;
    const x = side * (7.2 + Math.random() * 6.6);
    const z = 9 - Math.random() * 48;
    const size = 0.45 + Math.random() * 1.1;
    reedMatrix.compose(
      new THREE.Vector3(x, size * 0.35 - 0.05, z),
      new THREE.Quaternion(),
      new THREE.Vector3(size * 1.5, size * 0.65, size),
    );
    shrubs.setMatrixAt(index, reedMatrix);
  }
  scene.add(shrubs);

  const mistCanvas = document.createElement("canvas");
  mistCanvas.width = 128;
  mistCanvas.height = 64;
  const mistContext = mistCanvas.getContext("2d");
  const mistGradient = mistContext.createRadialGradient(64, 32, 3, 64, 32, 62);
  mistGradient.addColorStop(0, "rgba(204, 226, 224, 0.34)");
  mistGradient.addColorStop(0.48, "rgba(167, 204, 202, 0.15)");
  mistGradient.addColorStop(1, "rgba(123, 168, 169, 0)");
  mistContext.fillStyle = mistGradient;
  mistContext.fillRect(0, 0, 128, 64);
  const mistTexture = new THREE.CanvasTexture(mistCanvas);
  const mistMaterial = new THREE.SpriteMaterial({
    map: mistTexture,
    transparent: true,
    depthWrite: false,
    opacity: 0.38,
    color: 0xb8d1d0,
  });
  const mistSprites = [];
  for (let index = 0; index < 18; index += 1) {
    const mist = new THREE.Sprite(mistMaterial.clone());
    mist.position.set(
      (Math.random() - 0.5) * 15,
      0.25 + Math.random() * 1.4,
      7 - Math.random() * 40,
    );
    mist.scale.set(7 + Math.random() * 7, 1.4 + Math.random() * 1.8, 1);
    mist.userData.baseX = mist.position.x;
    mist.userData.phase = Math.random() * Math.PI * 2;
    mist.userData.speed = 0.08 + Math.random() * 0.08;
    scene.add(mist);
    mistSprites.push(mist);
  }

  const characterAnchor = new THREE.Group();
  characterAnchor.name = "LaLloronaCharacterAnchor";
  characterAnchor.position.set(-2.35, 0, -6.4);
  characterAnchor.rotation.y = 0;
  characterAnchor.userData.attachmentInterface = {
    format: "GLB/GLTF",
    units: "meters",
    feetAtLocalY: 0,
    facesLocalPositiveZ: true,
    targetStandingHeight: 3.15,
  };

  const placeholder = new THREE.Group();
  placeholder.name = "NeutralCharacterPlaceholder";
  const placeholderMaterial = new THREE.MeshBasicMaterial({
    color: 0xadc7c5,
    transparent: true,
    opacity: 0.12,
    depthWrite: false,
  });
  const placeholderBody = new THREE.Mesh(
    new THREE.CylinderGeometry(0.2, 0.48, 1.25, 10),
    placeholderMaterial,
  );
  placeholderBody.position.y = 0.72;
  const placeholderHead = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 12, 8),
    placeholderMaterial,
  );
  placeholderHead.position.y = 1.53;
  const placeholderRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.62, 0.018, 6, 32),
    placeholderMaterial,
  );
  placeholderRing.rotation.x = Math.PI / 2;
  placeholderRing.position.y = 0.03;
  placeholder.add(placeholderBody, placeholderHead, placeholderRing);
  characterAnchor.add(placeholder);
  scene.add(characterAnchor);

  const characterFill = new THREE.PointLight(0xd9eeec, 16, 10, 1.55);
  characterFill.position.set(-0.5, 3.1, 2.6);
  characterAnchor.add(characterFill);

  const characterRim = new THREE.SpotLight(0xb7e4e4, 22, 18, Math.PI / 4.5, 0.62, 1.25);
  characterRim.position.set(3.5, 7.5, -1.5);
  characterRim.target = characterAnchor;
  scene.add(characterRim);

  window.hadithi = window.hadithi || {};
  window.hadithi.laLloronaCharacterAnchor = characterAnchor;
  window.dispatchEvent(
    new CustomEvent("hadithi:la-llorona-anchor-ready", {
      detail: { anchor: characterAnchor },
    }),
  );

  const showModelFallback = () => {
    placeholder.visible = true;
    placeholderMaterial.opacity = 0.3;
    modelStatus.hidden = false;
    modelStatus.textContent = (
      "The character could not be loaded. A quiet riverbank silhouette remains in her place."
    );
  };

  const loadCharacter = () => {
    const loader = new GLTFLoader();
    loader.load(
      "/static/models/la-llorona-character-study.glb",
      (gltf) => {
        characterModel = gltf.scene;
        characterModel.name = "LaLloronaCharacter";
        characterModel.traverse((child) => {
          if (child.isMesh) {
            child.frustumCulled = false;
            child.renderOrder = 3;
            const materials = Array.isArray(child.material)
              ? child.material
              : [child.material];
            materials.forEach((material) => {
              material.transparent = false;
              material.opacity = 1;
              material.depthWrite = true;
              material.alphaTest = 0;
              material.side = THREE.DoubleSide;
              const moonlitColors = {
                dress: 0xd8e7ec,
                skin: 0x9fb4ba,
                nails: 0xaabcc0,
                eyes: 0xb8d3d8,
                hair: 0x11191d,
              };
              if (material.color && moonlitColors[material.name]) {
                material.color.setHex(moonlitColors[material.name]);
              }
              if (material.emissive) {
                material.emissive.setHex(
                  material.name === "hair" ? 0x030708 : 0x182b30,
                );
                material.emissiveIntensity = material.name === "dress" ? 0.32 : 0.18;
              }
              material.needsUpdate = true;
            });
          }
        });
        characterAnchor.add(characterModel);

        const idleClip = THREE.AnimationClip.findByName(
          gltf.animations,
          "Mournful_Idle",
        );
        if (idleClip) {
          characterMixer = new THREE.AnimationMixer(characterModel);
          const idleAction = characterMixer.clipAction(idleClip);
          idleAction.setLoop(THREE.LoopRepeat, Infinity);
          idleAction.play();
          characterMixer.update(0);
          activeAnimationName = idleClip.name;
        }
        characterAnchor.updateMatrixWorld(true);
        let posedBounds = new THREE.Box3().setFromObject(characterModel);
        let posedSize = posedBounds.getSize(new THREE.Vector3());
        if (!Number.isFinite(posedSize.y) || posedSize.y <= 0) {
          characterAnchor.remove(characterModel);
          characterModel = null;
          showModelFallback();
          return;
        }
        const scale = characterAnchor.userData.attachmentInterface.targetStandingHeight
          / posedSize.y;
        characterModel.scale.multiplyScalar(scale);
        characterAnchor.updateMatrixWorld(true);
        posedBounds = new THREE.Box3().setFromObject(characterModel);
        posedSize = posedBounds.getSize(new THREE.Vector3());
        const posedCenter = posedBounds.getCenter(new THREE.Vector3());
        const anchorWorldPosition = characterAnchor.getWorldPosition(new THREE.Vector3());
        characterModel.position.add(new THREE.Vector3(
          anchorWorldPosition.x - posedCenter.x,
          anchorWorldPosition.y - posedBounds.min.y,
          anchorWorldPosition.z - posedCenter.z,
        ));
        characterAnchor.updateMatrixWorld(true);
        placeholder.visible = false;
        characterAnchor.remove(placeholder);
        modelStatus.textContent = idleClip
          ? "La Llorona character loaded with Mournful Idle animation."
          : "La Llorona character loaded; the intended idle animation was unavailable.";
        window.setTimeout(() => {
          modelStatus.hidden = true;
        }, 3600);
        render();
      },
      undefined,
      (error) => {
        console.error("Could not load the La Llorona character model.", error);
        showModelFallback();
        render();
      },
    );
  };
  loadCharacter();

  const render = () => {
    renderer.render(scene, camera);
  };
  controls.addEventListener("change", render);

  const animate = (frameTime = 0) => {
    animationFrame = window.requestAnimationFrame(animate);
    if (document.hidden || frameTime - lastRenderedAt < 1000 / 30) {
      return;
    }
    lastRenderedAt = frameTime;
    const elapsed = frameTime / 1000;
    const animationDelta = Math.min(characterClock.getDelta(), 0.1);
    if (characterMixer && !reducedMotion) {
      characterMixer.update(animationDelta);
    }
    if (!reducedMotion) {
      waterUniforms.time.value = elapsed;
      mistSprites.forEach((mist) => {
        mist.position.x = mist.userData.baseX
          + Math.sin(elapsed * mist.userData.speed + mist.userData.phase) * 1.2;
        mist.material.opacity = 0.27
          + Math.sin(elapsed * 0.12 + mist.userData.phase) * 0.08;
      });
      controls.update();
    }
    render();
  };

  const resize = () => {
    const width = container.clientWidth;
    const height = container.clientHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.setSize(width, height, false);
    render();
  };
  window.addEventListener("resize", resize);

  const setAmbienceUi = (active, label, status = label) => {
    ambienceButton.disabled = false;
    ambienceButton.setAttribute("aria-pressed", String(active));
    ambienceButton.textContent = label;
    audioStatus.textContent = status;
  };

  const stopAmbience = () => {
    window.clearTimeout(ambienceTimer);
    ambienceTimer = null;
    ambienceStarting = false;
    setAmbienceUi(false, "Hear the river", "River ambience stopped.");
    if (!ambienceContext || !ambienceMaster) {
      ambienceNodes = [];
      return;
    }
    const context = ambienceContext;
    const nodes = ambienceNodes;
    ambienceNodes = [];
    ambienceMaster.gain.cancelScheduledValues(context.currentTime);
    ambienceMaster.gain.setTargetAtTime(0.0001, context.currentTime, 0.12);
    window.setTimeout(() => {
      nodes.forEach((node) => {
        if (typeof node.stop === "function") {
          try {
            node.stop();
          } catch {
            // A short scheduled tone may already have stopped.
          }
        }
        node.disconnect();
      });
      context.close().catch(() => {});
    }, 380);
    ambienceContext = null;
    ambienceMaster = null;
    ambienceAnalyser = null;
  };

  const startAmbience = async () => {
    if (ambienceStarting || ambienceContext) {
      return;
    }
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      setAmbienceUi(false, "Audio unavailable", "Web Audio is unavailable in this browser.");
      return;
    }
    ambienceStarting = true;
    ambienceButton.disabled = true;
    ambienceButton.textContent = "Starting river...";
    audioStatus.textContent = "Starting river ambience.";

    const context = new AudioContextClass({ latencyHint: "interactive" });
    ambienceContext = context;
    await context.resume();
    if (context.state !== "running") {
      throw new Error(`Audio context did not start; current state is ${context.state}.`);
    }

    const master = context.createGain();
    master.gain.setValueAtTime(0.0001, context.currentTime);
    master.gain.exponentialRampToValueAtTime(0.16, context.currentTime + 0.65);
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    master.connect(analyser).connect(context.destination);
    ambienceMaster = master;
    ambienceAnalyser = analyser;

    const noiseBuffer = context.createBuffer(
      1,
      context.sampleRate * 4,
      context.sampleRate,
    );
    const noiseData = noiseBuffer.getChannelData(0);
    let slowWater = 0;
    for (let index = 0; index < noiseData.length; index += 1) {
      const whiteWater = Math.random() * 2 - 1;
      slowWater = slowWater * 0.97 + whiteWater * 0.03;
      noiseData[index] = whiteWater * 0.32 + slowWater * 1.7;
    }
    const riverNoise = context.createBufferSource();
    const riverHighpass = context.createBiquadFilter();
    const riverLowpass = context.createBiquadFilter();
    const riverGain = context.createGain();
    riverNoise.buffer = noiseBuffer;
    riverNoise.loop = true;
    riverHighpass.type = "highpass";
    riverHighpass.frequency.value = 90;
    riverLowpass.type = "lowpass";
    riverLowpass.frequency.value = 2400;
    riverLowpass.Q.value = 0.4;
    riverGain.gain.value = 0.62;
    riverNoise
      .connect(riverHighpass)
      .connect(riverLowpass)
      .connect(riverGain)
      .connect(master);
    riverNoise.start();

    const waterPulse = context.createOscillator();
    const waterPulseDepth = context.createGain();
    waterPulse.type = "sine";
    waterPulse.frequency.value = 0.09;
    waterPulseDepth.gain.value = 0.07;
    waterPulse.connect(waterPulseDepth).connect(riverGain.gain);
    waterPulse.start();

    const drone = context.createOscillator();
    const droneGain = context.createGain();
    drone.type = "sine";
    drone.frequency.value = 98;
    droneGain.gain.value = 0.022;
    drone.connect(droneGain).connect(master);
    drone.start();
    ambienceNodes = [
      riverNoise,
      riverHighpass,
      riverLowpass,
      riverGain,
      waterPulse,
      waterPulseDepth,
      drone,
      droneGain,
      master,
      analyser,
    ];

    const scheduleReedTone = () => {
      if (!ambienceContext || !ambienceMaster || ambienceContext.state === "closed") {
        return;
      }
      const now = context.currentTime;
      const tone = context.createOscillator();
      const toneGain = context.createGain();
      tone.type = "sine";
      tone.frequency.value = [164.81, 196, 220][Math.floor(Math.random() * 3)];
      toneGain.gain.setValueAtTime(0.0001, now);
      toneGain.gain.exponentialRampToValueAtTime(0.04, now + 0.35);
      toneGain.gain.exponentialRampToValueAtTime(0.0001, now + 2.8);
      tone.connect(toneGain).connect(master);
      tone.addEventListener("ended", () => {
        tone.disconnect();
        toneGain.disconnect();
      }, { once: true });
      tone.start(now);
      tone.stop(now + 3);
      ambienceTimer = window.setTimeout(scheduleReedTone, 6000 + Math.random() * 7000);
    };
    scheduleReedTone();
    context.addEventListener("statechange", () => {
      if (ambienceContext !== context) {
        return;
      }
      if (context.state === "suspended") {
        setAmbienceUi(false, "Resume the river", "River ambience is paused.");
      }
    });
    ambienceStarting = false;
    setAmbienceUi(true, "Quiet the river", "River ambience is playing.");
  };

  ambienceButton.addEventListener("click", async () => {
    if (ambienceContext) {
      if (ambienceContext.state === "suspended") {
        try {
          await ambienceContext.resume();
          if (ambienceContext.state !== "running") {
            throw new Error(`Audio context remains ${ambienceContext.state}.`);
          }
          setAmbienceUi(true, "Quiet the river", "River ambience resumed.");
        } catch (error) {
          console.error("Could not resume La Llorona river ambience.", error);
          setAmbienceUi(
            false,
            "Try river sound again",
            "The river ambience could not resume. Tap to try again.",
          );
        }
      } else {
        stopAmbience();
      }
    } else {
      try {
        await startAmbience();
      } catch (error) {
        console.error("Could not start La Llorona river ambience.", error);
        stopAmbience();
        setAmbienceUi(
          false,
          "Try river sound again",
          "The river ambience could not start. Tap to try again.",
        );
      }
    }
  });

  window.hadithi.getLaLloronaAmbienceState = () => {
    let outputRms = 0;
    if (ambienceAnalyser) {
      const samples = new Float32Array(ambienceAnalyser.fftSize);
      ambienceAnalyser.getFloatTimeDomainData(samples);
      const sumOfSquares = samples.reduce(
        (total, sample) => total + sample * sample,
        0,
      );
      outputRms = Math.sqrt(sumOfSquares / samples.length);
    }
    return {
      state: ambienceContext?.state || "inactive",
      masterGain: ambienceMaster?.gain.value || 0,
      outputRms,
      nodeCount: ambienceNodes.length,
    };
  };
  window.hadithi.getLaLloronaCharacterState = () => {
    const bounds = characterModel
      ? new THREE.Box3().setFromObject(characterModel)
      : null;
    const center = bounds
      ? bounds.getCenter(new THREE.Vector3())
      : null;
    const projectedCenter = center
      ? center.clone().project(camera)
      : null;
    return {
      modelLoaded: Boolean(characterModel?.parent),
      animation: activeAnimationName,
      placeholderVisible: placeholder.parent === characterAnchor && placeholder.visible,
      anchorPosition: characterAnchor.position.toArray(),
      modelScale: characterModel?.scale.toArray() || null,
      boundsMin: bounds?.min.toArray() || null,
      boundsMax: bounds?.max.toArray() || null,
      projectedCenter: projectedCenter?.toArray() || null,
    };
  };

  const addChatMessage = (role, text, sources = [], metadata = "") => {
    const bubble = document.createElement("article");
    bubble.className = `chat-bubble ${role}`;
    const copy = document.createElement("p");
    copy.textContent = text;
    bubble.append(copy);
    if (sources.length) {
      const citations = document.createElement("div");
      citations.className = "llorona-citations";
      sources.forEach((source) => {
        const citation = document.createElement("a");
        citation.href = source.url;
        citation.target = "_blank";
        citation.rel = "noreferrer";
        citation.textContent = source.organization;
        citation.title = `${source.title}. ${source.role}`;
        citations.append(citation);
      });
      bubble.append(citations);
    }
    if (metadata) {
      const meta = document.createElement("small");
      meta.className = "chat-meta";
      meta.textContent = metadata;
      bubble.append(meta);
    }
    chatMessages.append(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  };

  const setChatBusy = (busy, status = "") => {
    chatBusy = busy;
    questionInput.disabled = busy;
    languageSelect.disabled = busy;
    sendButton.disabled = busy;
    sendButton.textContent = busy ? "…" : "→";
    chatStatus.textContent = status;
  };

  const submitQuestion = async (question) => {
    if (chatBusy) {
      return;
    }
    const requestHistory = conversationHistory.slice(-6);
    addChatMessage("user", question);
    questionInput.value = "";
    setChatBusy(
      true,
      languageSelect.value === "es"
        ? "Consultando las fuentes aprobadas…"
        : "Consulting approved sources…",
    );
    try {
      const response = await fetch("/api/legends/la-llorona/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          language: languageSelect.value,
          history: requestHistory,
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(result.detail)
          ? result.detail.map((item) => item.msg).filter(Boolean).join(" ")
          : result.detail;
        throw new Error(detail || "The conversation could not continue.");
      }
      const answer = result.follow_up
        ? `${result.answer} ${result.follow_up}`
        : result.answer;
      const generator = result.generator || "verified-fallback";
      const metadata = generator === "local-conversation"
        ? "Conversation · research draft"
        : generator === "verified-fallback"
          ? "Verified source response · research draft"
          : "Generated from approved sources · research draft";
      addChatMessage("assistant", answer, result.sources || [], metadata);
      conversationHistory.push(
        { role: "user", content: question },
        { role: "assistant", content: answer },
      );
      if (conversationHistory.length > 6) {
        conversationHistory.splice(0, conversationHistory.length - 6);
      }
      if (result.generation_warning) {
        addChatMessage("system", result.generation_warning);
      }
      chatStatus.textContent = result.sources?.length
        ? (
          languageSelect.value === "es"
            ? `${result.sources.length} fuente(s) visible(s) en la respuesta.`
            : `${result.sources.length} source(s) linked in the response.`
        )
        : (
          languageSelect.value === "es"
            ? "La respuesta no cita una fuente aprobada."
            : "The response does not cite an approved source."
        );
    } catch (error) {
      addChatMessage(
        "system",
        error.message || "The conversation could not continue. Please try again.",
      );
      chatStatus.textContent = (
        languageSelect.value === "es"
          ? "No se pudo completar la respuesta."
          : "The response could not be completed."
      );
    } finally {
      setChatBusy(false, chatStatus.textContent);
      questionInput.focus();
    }
  };

  questionForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const question = questionInput.value.trim();
    if (question) {
      submitQuestion(question);
    }
  });

  questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      questionForm.requestSubmit();
    }
  });

  languageSelect.addEventListener("change", () => {
    const spanish = languageSelect.value === "es";
    questionInput.placeholder = spanish
      ? "Pregunta por una versión regional…"
      : "Ask about a regional telling…";
    chatStatus.textContent = spanish
      ? "Las respuestas conservarán las diferencias regionales."
      : "Answers will preserve regional differences.";
  });

  const handleMotionPreference = (event) => {
    reducedMotion = event.matches;
    controls.enableDamping = !reducedMotion;
    waterUniforms.time.value = 0;
    render();
  };
  reducedMotionQuery.addEventListener("change", handleMotionPreference);

  loading.hidden = true;
  if (reducedMotion) {
    render();
  } else {
    animate();
  }

  window.addEventListener("pagehide", () => {
    stopAmbience();
    window.cancelAnimationFrame(animationFrame);
    controls.dispose();
    if (characterMixer) {
      characterMixer.stopAllAction();
    }
    if (characterModel) {
      characterAnchor.remove(characterModel);
    }
    renderer.dispose();
    mistTexture.dispose();
  }, { once: true });
}
