import * as THREE from "three";
import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/loaders/GLTFLoader.js";

const container = document.querySelector("#legendScene");

if (container) {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.prepend(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x010207);

  const camera = new THREE.PerspectiveCamera(
    44,
    container.clientWidth / container.clientHeight,
    0.05,
    500,
  );
  camera.position.set(0, 0.25, 8.2);

  const clock = new THREE.Clock();
  let journeyStartedAt = null;
  let landscapeActive = false;
  let guideSpeaking = false;
  let targetCameraPosition = null;
  let loadedHeadBone = null;
  let loadedJawBone = null;
  let loadedHeadBaseRotationY = 0;
  let loadedJawBaseRotationX = 0;
  let loadedLeftUpperArm = null;
  let loadedRightUpperArm = null;
  let loadedLeftLowerArm = null;
  let loadedRightLowerArm = null;
  const armBaseQuaternions = new Map();
  let warriorBaseY = 0.85;
  let activeGuideGesture = "neutral";
  const gestureQuaternion = new THREE.Quaternion();
  const gestureXAxis = new THREE.Vector3(1, 0, 0);
  const gestureZAxis = new THREE.Vector3(0, 0, 1);

  const starGeometry = new THREE.BufferGeometry();
  const starPositions = new Float32Array(2600 * 3);
  for (let index = 0; index < starPositions.length; index += 3) {
    const radius = 35 + Math.random() * 110;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    starPositions[index] = radius * Math.sin(phi) * Math.cos(theta);
    starPositions[index + 1] = radius * Math.cos(phi);
    starPositions[index + 2] = radius * Math.sin(phi) * Math.sin(theta);
  }
  starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
  const stars = new THREE.Points(
    starGeometry,
    new THREE.PointsMaterial({
      color: 0xe5efff,
      size: 0.12,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.88,
    }),
  );
  scene.add(stars);

  const cosmosGroup = new THREE.Group();
  scene.add(cosmosGroup);

  const textureLoader = new THREE.TextureLoader();
  const earthTexture = textureLoader.load(
    "https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg",
  );
  earthTexture.colorSpace = THREE.SRGBColorSpace;

  const earth = new THREE.Mesh(
    new THREE.SphereGeometry(2.15, 96, 96),
    new THREE.MeshStandardMaterial({
      map: earthTexture,
      roughness: 0.78,
      metalness: 0,
    }),
  );
  cosmosGroup.add(earth);

  const atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(2.2, 64, 64),
    new THREE.MeshBasicMaterial({
      color: 0x4ea1ff,
      transparent: true,
      opacity: 0.12,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
    }),
  );
  cosmosGroup.add(atmosphere);

  const cosmosLight = new THREE.DirectionalLight(0xffffff, 4.2);
  cosmosLight.position.set(7, 4, 7);
  scene.add(cosmosLight);
  scene.add(new THREE.AmbientLight(0x294363, 0.55));

  const latLonToVector = (latitude, longitude, radius = 2.18) => {
    const lat = THREE.MathUtils.degToRad(latitude);
    const lon = THREE.MathUtils.degToRad(longitude);
    return new THREE.Vector3(
      radius * Math.cos(lat) * Math.sin(lon),
      radius * Math.sin(lat),
      radius * Math.cos(lat) * Math.cos(lon),
    );
  };

  const destinations = [
    { id: "luanda-magere", latitude: -0.1, longitude: 34.75, active: true },
    { id: "anansi", latitude: 7.95, longitude: -1.03 },
    { id: "sundiata", latitude: 17.57, longitude: -3.99 },
    { id: "la-llorona", latitude: 23.63, longitude: -102.55 },
    { id: "el-cadejo", latitude: 14.62, longitude: -90.52 },
  ];

  let kenyaMarker;
  destinations.forEach((destination) => {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(destination.active ? 0.075 : 0.045, 18, 18),
      new THREE.MeshBasicMaterial({
        color: destination.active ? 0xffa72f : 0xb6d3ff,
        transparent: true,
        opacity: destination.active ? 1 : 0.7,
      }),
    );
    marker.position.copy(latLonToVector(destination.latitude, destination.longitude));
    marker.userData.destination = destination.id;
    earth.add(marker);

    if (destination.active) {
      kenyaMarker = marker;
      const halo = new THREE.Mesh(
        new THREE.RingGeometry(0.1, 0.16, 32),
        new THREE.MeshBasicMaterial({
          color: 0xffbd58,
          transparent: true,
          opacity: 0.75,
          side: THREE.DoubleSide,
        }),
      );
      halo.lookAt(new THREE.Vector3(0, 0, 0));
      marker.add(halo);
    }
  });

  const landscapeGroup = new THREE.Group();
  landscapeGroup.visible = false;
  scene.add(landscapeGroup);

  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(85, 32, 18),
    new THREE.MeshBasicMaterial({ color: 0x172c33, side: THREE.BackSide }),
  );
  landscapeGroup.add(sky);

  const hemiLight = new THREE.HemisphereLight(0xffd399, 0x193a2f, 1.75);
  landscapeGroup.add(hemiLight);

  const sunLight = new THREE.DirectionalLight(0xffd08a, 5.5);
  sunLight.castShadow = true;
  sunLight.shadow.mapSize.set(2048, 2048);
  sunLight.shadow.camera.left = -13;
  sunLight.shadow.camera.right = 13;
  sunLight.shadow.camera.top = 13;
  sunLight.shadow.camera.bottom = -13;
  landscapeGroup.add(sunLight);
  landscapeGroup.add(sunLight.target);

  const sunMesh = new THREE.Mesh(
    new THREE.SphereGeometry(0.85, 32, 32),
    new THREE.MeshBasicMaterial({ color: 0xffc85a }),
  );
  landscapeGroup.add(sunMesh);

  const terrainHeightAt = (x, z) =>
    Math.sin(x * 0.2) * 0.25
    + Math.cos(z * 0.17) * 0.19
    + Math.sin((x - z) * 0.08) * 0.13;

  const groundGeometry = new THREE.PlaneGeometry(70, 70, 48, 48);
  const groundPositions = groundGeometry.attributes.position;
  for (let index = 0; index < groundPositions.count; index += 1) {
    const x = groundPositions.getX(index);
    const y = groundPositions.getY(index);
    groundPositions.setZ(index, terrainHeightAt(x, -y));
  }
  groundGeometry.computeVertexNormals();
  const ground = new THREE.Mesh(
    groundGeometry,
    new THREE.MeshStandardMaterial({ color: 0x4d6b3d, roughness: 0.97 }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  landscapeGroup.add(ground);

  const mountainMaterial = new THREE.MeshStandardMaterial({
    color: 0x29493d,
    roughness: 1,
  });
  [
    [-15, -17, 6, 7],
    [-8, -19, 5, 8],
    [8, -18, 7, 10],
    [17, -21, 8, 11],
  ].forEach(([x, z, radius, height], index) => {
    const mountain = new THREE.Mesh(
      new THREE.ConeGeometry(radius, height, 7),
      mountainMaterial,
    );
    mountain.position.set(x, height / 2 - 0.3, z);
    mountain.rotation.y = index * 0.55;
    landscapeGroup.add(mountain);
  });

  const path = new THREE.Mesh(
    new THREE.PlaneGeometry(2.5, 38),
    new THREE.MeshStandardMaterial({ color: 0xa66f3d, roughness: 1 }),
  );
  path.rotation.x = -Math.PI / 2;
  path.rotation.z = -0.1;
  path.position.set(3.2, 0.035, -7);
  path.receiveShadow = true;
  landscapeGroup.add(path);

  const treeTrunkMaterial = new THREE.MeshStandardMaterial({
    color: 0x4f2d1d,
    roughness: 0.96,
  });
  const treeCanopyMaterial = new THREE.MeshStandardMaterial({
    color: 0x274d32,
    roughness: 0.92,
  });

  const createAcaciaTree = (x, z, scale = 1, rotation = 0) => {
    const tree = new THREE.Group();
    const trunk = new THREE.Mesh(
      new THREE.CylinderGeometry(0.13, 0.24, 2.7, 9),
      treeTrunkMaterial,
    );
    trunk.position.y = 1.35;
    trunk.castShadow = true;
    tree.add(trunk);

    [
      [-0.62, 2.25, -0.62],
      [0.58, 2.35, 0.58],
    ].forEach(([branchX, branchY, branchRotation]) => {
      const branch = new THREE.Mesh(
        new THREE.CylinderGeometry(0.07, 0.12, 1.55, 8),
        treeTrunkMaterial,
      );
      branch.position.set(branchX * 0.52, branchY, 0);
      branch.rotation.z = branchRotation;
      branch.castShadow = true;
      tree.add(branch);
    });

    [
      [-0.95, 3.05, 0.2, 1.5],
      [0.55, 3.12, -0.2, 1.7],
      [0, 3.35, 0, 1.9],
    ].forEach(([canopyX, canopyY, canopyZ, canopyScale]) => {
      const canopy = new THREE.Mesh(
        new THREE.IcosahedronGeometry(1, 1),
        treeCanopyMaterial,
      );
      canopy.position.set(canopyX, canopyY, canopyZ);
      canopy.scale.set(canopyScale, 0.42, canopyScale * 0.72);
      canopy.castShadow = true;
      tree.add(canopy);
    });

    tree.position.set(x, terrainHeightAt(x, z), z);
    tree.rotation.y = rotation;
    tree.scale.setScalar(scale);
    landscapeGroup.add(tree);
  };

  [
    [-11, -6, 1.3, 0.3],
    [-7.5, -12, 1.55, -0.4],
    [4.5, -14, 1.25, 0.7],
    [9, -8.5, 1.5, -0.2],
    [13.5, -12, 1.8, 0.5],
    [16, -4.5, 1.1, -0.6],
  ].forEach((tree) => createAcaciaTree(...tree));

  const hutWallMaterial = new THREE.MeshStandardMaterial({
    color: 0x9a6036,
    roughness: 1,
  });
  const hutRoofMaterial = new THREE.MeshStandardMaterial({
    color: 0x5e3b20,
    roughness: 1,
  });
  const hutDoorMaterial = new THREE.MeshStandardMaterial({
    color: 0x1b130e,
    roughness: 1,
  });

  const createHut = (x, z, scale = 1) => {
    const hut = new THREE.Group();
    const wall = new THREE.Mesh(
      new THREE.CylinderGeometry(1.05, 1.12, 1.45, 18),
      hutWallMaterial,
    );
    wall.position.y = 0.72;
    wall.castShadow = true;
    wall.receiveShadow = true;
    const roof = new THREE.Mesh(
      new THREE.ConeGeometry(1.42, 1.15, 18),
      hutRoofMaterial,
    );
    roof.position.y = 2.02;
    roof.castShadow = true;
    const door = new THREE.Mesh(
      new THREE.BoxGeometry(0.42, 0.88, 0.08),
      hutDoorMaterial,
    );
    door.position.set(0, 0.45, 1.08);
    hut.add(wall, roof, door);
    hut.position.set(x, terrainHeightAt(x, z), z);
    hut.scale.setScalar(scale);
    landscapeGroup.add(hut);
  };

  createHut(4.6, -9.5, 0.92);
  createHut(8.1, -11.8, 0.78);
  createHut(-5.8, -11.2, 0.72);

  const grassGeometry = new THREE.ConeGeometry(0.055, 0.52, 4);
  const grassMaterial = new THREE.MeshStandardMaterial({
    color: 0x385b2c,
    roughness: 1,
  });
  const grass = new THREE.InstancedMesh(grassGeometry, grassMaterial, 190);
  const grassMatrix = new THREE.Matrix4();
  const grassQuaternion = new THREE.Quaternion();
  const grassScale = new THREE.Vector3();
  for (let index = 0; index < grass.count; index += 1) {
    const x = (Math.random() - 0.5) * 38;
    const z = (Math.random() - 0.5) * 28 - 3;
    const heightScale = 0.55 + Math.random() * 1.15;
    grassQuaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.random() * Math.PI);
    grassScale.set(1, heightScale, 1);
    grassMatrix.compose(
      new THREE.Vector3(x, terrainHeightAt(x, z) + 0.25 * heightScale, z),
      grassQuaternion,
      grassScale,
    );
    grass.setMatrixAt(index, grassMatrix);
  }
  grass.receiveShadow = true;
  landscapeGroup.add(grass);

  let warrior = new THREE.Group();
  const skin = new THREE.MeshStandardMaterial({
    color: 0x4a2315,
    roughness: 0.72,
    metalness: 0,
  });
  const cloth = new THREE.MeshStandardMaterial({
    color: 0x211b16,
    roughness: 0.92,
  });
  const leather = new THREE.MeshStandardMaterial({
    color: 0x6d321f,
    roughness: 0.78,
  });

  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.85, 2.1, 16), skin);
  torso.position.y = 2.15;
  torso.scale.x = 1.28;
  const chest = new THREE.Mesh(new THREE.SphereGeometry(0.82, 18, 14), skin);
  chest.scale.set(1.28, 0.72, 0.65);
  chest.position.y = 2.75;
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.43, 20, 16), skin);
  head.scale.set(0.9, 1.08, 0.92);
  head.position.y = 3.75;
  const waist = new THREE.Mesh(new THREE.CylinderGeometry(0.74, 0.8, 0.75, 12), cloth);
  waist.position.y = 1.25;

  const createLimb = (radiusTop, radiusBottom, length, material) => {
    const limb = new THREE.Mesh(
      new THREE.CylinderGeometry(radiusTop, radiusBottom, length, 12),
      material,
    );
    limb.castShadow = true;
    return limb;
  };
  const leftArm = createLimb(0.24, 0.2, 1.85, skin);
  leftArm.position.set(-1.04, 2.3, 0);
  leftArm.rotation.z = -0.12;
  const rightArm = createLimb(0.24, 0.2, 1.85, skin);
  rightArm.position.set(1.04, 2.3, 0);
  rightArm.rotation.z = 0.12;
  const leftLeg = createLimb(0.31, 0.23, 1.75, skin);
  leftLeg.position.set(-0.38, 0.35, 0);
  const rightLeg = createLimb(0.31, 0.23, 1.75, skin);
  rightLeg.position.set(0.38, 0.35, 0);
  const shield = new THREE.Mesh(new THREE.CylinderGeometry(0.98, 0.98, 0.13, 32), leather);
  shield.rotation.x = Math.PI / 2;
  shield.position.set(-1.17, 2.1, 0.27);
  shield.castShadow = true;
  const spear = new THREE.Mesh(
    new THREE.CylinderGeometry(0.04, 0.04, 5.3, 10),
    new THREE.MeshStandardMaterial({ color: 0x5b321b, roughness: 0.8 }),
  );
  spear.position.set(1.22, 2.05, 0);
  spear.rotation.z = -0.08;

  [torso, chest, head, waist, leftArm, rightArm, leftLeg, rightLeg, spear].forEach((part) => {
    part.castShadow = true;
  });
  warrior.add(
    torso,
    chest,
    head,
    waist,
    leftArm,
    rightArm,
    leftLeg,
    rightLeg,
    shield,
    spear,
  );
  warrior.position.set(-1.4, 0.85, -0.5);
  landscapeGroup.add(warrior);

  const loadConfiguredWarrior = async () => {
    try {
      const response = await fetch("/static/models/warrior-model.json");
      if (!response.ok) {
        return;
      }
      const modelConfig = await response.json();
      if (!modelConfig.enabled || !modelConfig.path) {
        return;
      }
      const loader = new GLTFLoader();
      loader.load(
        modelConfig.path,
        (gltf) => {
          const loadedWarrior = gltf.scene;
          const [modelX, modelYOffset, modelZ] = modelConfig.position || [-1.4, 0, -0.5];
          warriorBaseY = terrainHeightAt(modelX, modelZ) + modelYOffset;
          loadedWarrior.position.set(modelX, warriorBaseY, modelZ);
          loadedWarrior.rotation.fromArray(modelConfig.rotation || [0, 0, 0]);
          loadedWarrior.scale.setScalar(modelConfig.scale || 1);
          loadedWarrior.traverse((object) => {
            if (object.isMesh) {
              object.castShadow = true;
              object.receiveShadow = true;
              if (object.material?.name === "male_muscle_13290.obj") {
                object.material.metalness = 0;
                object.material.roughness = 0.68;
              }
            }
          });
          loadedHeadBone = loadedWarrior.getObjectByName("head_AFRICANWARRIORrig");
          loadedJawBone = loadedWarrior.getObjectByName("jaw_AFRICANWARRIORrig");
          loadedLeftUpperArm = loadedWarrior.getObjectByName("upperarm01.L_AFRICANWARRIORrig");
          loadedRightUpperArm = loadedWarrior.getObjectByName("upperarm01.R_AFRICANWARRIORrig");
          loadedLeftLowerArm = loadedWarrior.getObjectByName("lowerarm01.L_AFRICANWARRIORrig");
          loadedRightLowerArm = loadedWarrior.getObjectByName("lowerarm01.R_AFRICANWARRIORrig");
          loadedHeadBaseRotationY = loadedHeadBone?.rotation.y || 0;
          loadedJawBaseRotationX = loadedJawBone?.rotation.x || 0;
          [
            loadedLeftUpperArm,
            loadedRightUpperArm,
            loadedLeftLowerArm,
            loadedRightLowerArm,
          ].filter(Boolean).forEach((bone) => {
            armBaseQuaternions.set(bone, bone.quaternion.clone());
          });
          landscapeGroup.remove(warrior);
          warrior = loadedWarrior;
          landscapeGroup.add(warrior);
        },
        undefined,
        () => {
          showVoiceMessage("The detailed character could not load, so the lightweight guide remains active.");
        },
      );
    } catch {
      // The procedural guide remains available until the licensed GLB is configured.
    }
  };
  loadConfiguredWarrior();

  const stone = new THREE.Mesh(
    new THREE.DodecahedronGeometry(1.25, 1),
    new THREE.MeshStandardMaterial({ color: 0x676354, roughness: 1 }),
  );
  stone.scale.set(1.5, 0.62, 1.05);
  stone.position.set(5.2, 0.72, -3.6);
  stone.rotation.set(0.16, 0.72, 0.08);
  stone.castShadow = true;
  stone.receiveShadow = true;
  landscapeGroup.add(stone);

  const landscapeParticlesGeometry = new THREE.BufferGeometry();
  const landscapeParticlePositions = new Float32Array(330 * 3);
  for (let index = 0; index < landscapeParticlePositions.length; index += 3) {
    landscapeParticlePositions[index] = (Math.random() - 0.5) * 30;
    landscapeParticlePositions[index + 1] = Math.random() * 7;
    landscapeParticlePositions[index + 2] = (Math.random() - 0.5) * 25;
  }
  landscapeParticlesGeometry.setAttribute(
    "position",
    new THREE.BufferAttribute(landscapeParticlePositions, 3),
  );
  const landscapeParticles = new THREE.Points(
    landscapeParticlesGeometry,
    new THREE.PointsMaterial({
      color: 0xffd783,
      size: 0.045,
      transparent: true,
      opacity: 0.7,
    }),
  );
  landscapeGroup.add(landscapeParticles);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enabled = false;
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.minDistance = 5.5;
  controls.maxDistance = 18;
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.target.set(0, 2.2, -1);

  const updateSun = (degrees) => {
    const angle = THREE.MathUtils.degToRad(Number(degrees));
    const radius = 14;
    const position = new THREE.Vector3(
      Math.cos(angle) * radius,
      Math.max(2.5, Math.sin(angle) * 11),
      5,
    );
    sunMesh.position.copy(position);
    sunLight.position.copy(position);
    sunLight.target.position.copy(warrior.position);
  };
  updateSun(48);

  const enterPortal = document.querySelector("#enterPortal");
  const immersiveControls = document.querySelector("#immersiveControls");
  const locationMarker = document.querySelector("#locationMarker");
  const captionPanel = document.querySelector("#captionPanel");
  const guideAnswer = document.querySelector("#guideAnswer");
  const legendChat = document.querySelector("#legendChat");
  const chatMessages = document.querySelector("#chatMessages");
  const sourcePanel = document.querySelector("#sourcePanel");
  const guideSources = document.querySelector("#guideSources");
  const voiceStatus = document.querySelector("#voiceStatus");
  const questionForm = document.querySelector("#legendQuestionForm");
  const questionInput = document.querySelector("#legendQuestion");
  const guideLanguage = document.querySelector("#guideLanguage");
  const sunPanel = document.querySelector("#sunPanel");
  const toggleAmbienceButton = document.querySelector("#toggleAmbience");
  const voiceQuestionButton = document.querySelector("#voiceQuestion");
  const conversationHistory = [];
  const voiceInvitation = document.querySelector("#voiceInvitation");
  const toggleKeyboardButton = document.querySelector("#toggleKeyboard");
  let voiceInvitationTimer;
  let voiceRecorder = null;
  let voiceStream = null;
  let voiceChunks = [];
  let voiceStopTimer = null;
  let voiceRecordingStartedAt = 0;
  let activeNarrationAudio = null;
  let activeNarrationUrl = null;
  let ambienceContext = null;
  let ambienceMaster = null;
  let ambienceTimer = null;
  let lastRenderedAt = 0;

  const stopNarration = () => {
    window.speechSynthesis?.cancel();
    if (activeNarrationAudio) {
      activeNarrationAudio.pause();
      activeNarrationAudio = null;
    }
    if (activeNarrationUrl) {
      URL.revokeObjectURL(activeNarrationUrl);
      activeNarrationUrl = null;
    }
    guideSpeaking = false;
  };

  const addChatMessage = (role, text, metadata = null) => {
    const bubble = document.createElement("article");
    bubble.className = `chat-bubble ${role}`;
    bubble.textContent = text;
    if (metadata) {
      const meta = document.createElement("small");
      meta.className = "chat-meta";
      meta.textContent = metadata;
      bubble.append(meta);
    }
    chatMessages.append(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  };

  const stopAmbience = () => {
    window.clearTimeout(ambienceTimer);
    ambienceTimer = null;
    toggleAmbienceButton.classList.remove("active");
    toggleAmbienceButton.setAttribute("aria-pressed", "false");
    if (!ambienceContext || !ambienceMaster) {
      return;
    }
    const context = ambienceContext;
    ambienceMaster.gain.cancelScheduledValues(context.currentTime);
    ambienceMaster.gain.setTargetAtTime(0, context.currentTime, 0.18);
    window.setTimeout(() => context.close(), 500);
    ambienceContext = null;
    ambienceMaster = null;
  };

  const startAmbience = async () => {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      showVoiceMessage("Ambient audio is unavailable in this browser.");
      return;
    }
    ambienceContext = new AudioContextClass();
    ambienceMaster = ambienceContext.createGain();
    ambienceMaster.gain.value = 0.035;
    ambienceMaster.connect(ambienceContext.destination);

    [110, 164.81].forEach((frequency, index) => {
      const oscillator = ambienceContext.createOscillator();
      const gain = ambienceContext.createGain();
      oscillator.type = index ? "sine" : "triangle";
      oscillator.frequency.value = frequency;
      gain.gain.value = index ? 0.08 : 0.12;
      oscillator.connect(gain).connect(ambienceMaster);
      oscillator.start();
    });

    const noiseBuffer = ambienceContext.createBuffer(
      1,
      ambienceContext.sampleRate * 2,
      ambienceContext.sampleRate,
    );
    const noiseData = noiseBuffer.getChannelData(0);
    for (let index = 0; index < noiseData.length; index += 1) {
      noiseData[index] = Math.random() * 2 - 1;
    }
    const noise = ambienceContext.createBufferSource();
    const filter = ambienceContext.createBiquadFilter();
    const noiseGain = ambienceContext.createGain();
    noise.buffer = noiseBuffer;
    noise.loop = true;
    filter.type = "lowpass";
    filter.frequency.value = 520;
    noiseGain.gain.value = 0.045;
    noise.connect(filter).connect(noiseGain).connect(ambienceMaster);
    noise.start();

    const scheduleTone = () => {
      if (!ambienceContext || !ambienceMaster) {
        return;
      }
      const notes = [220, 246.94, 293.66, 329.63, 392];
      const oscillator = ambienceContext.createOscillator();
      const gain = ambienceContext.createGain();
      const now = ambienceContext.currentTime;
      oscillator.type = "sine";
      oscillator.frequency.value = notes[Math.floor(Math.random() * notes.length)];
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(0.22, now + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 1.7);
      oscillator.connect(gain).connect(ambienceMaster);
      oscillator.start(now);
      oscillator.stop(now + 1.8);
      ambienceTimer = window.setTimeout(scheduleTone, 2600 + Math.random() * 2800);
    };
    scheduleTone();
    await ambienceContext.resume();
    toggleAmbienceButton.classList.add("active");
    toggleAmbienceButton.setAttribute("aria-pressed", "true");
  };

  const animateSilentReply = (text) => {
    guideSpeaking = true;
    window.setTimeout(() => {
      if (!activeNarrationAudio) {
        guideSpeaking = false;
      }
    }, Math.min(6500, Math.max(1800, text.length * 32)));
  };

  const speak = async (text, language = "en") => {
    guideAnswer.textContent = text;
    stopNarration();
    try {
      const response = await fetch("/api/speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language }),
      });
      if (!response.ok) {
        animateSilentReply(text);
        return;
      }
      const audioBlob = await response.blob();
      activeNarrationUrl = URL.createObjectURL(audioBlob);
      activeNarrationAudio = new Audio(activeNarrationUrl);
      activeNarrationAudio.addEventListener("playing", () => {
        guideSpeaking = true;
      });
      activeNarrationAudio.addEventListener("ended", stopNarration, { once: true });
      activeNarrationAudio.addEventListener("error", () => {
        stopNarration();
        animateSilentReply(text);
      }, { once: true });
      await activeNarrationAudio.play();
    } catch {
      stopNarration();
      animateSilentReply(text);
    }
  };

  const enterLandscape = () => {
    cosmosGroup.visible = false;
    stars.material.opacity = 0.42;
    landscapeGroup.visible = true;
    landscapeActive = true;
    scene.fog = new THREE.FogExp2(0x142a2a, 0.014);
    camera.position.set(8.6, 5.2, 10.8);
    controls.enabled = true;
    immersiveControls.hidden = false;
    legendChat.hidden = false;
    voiceInvitation.hidden = false;
    voiceInvitationTimer = window.setTimeout(() => {
      voiceInvitation.classList.add("leaving");
      window.setTimeout(() => {
        voiceInvitation.hidden = true;
        voiceInvitation.classList.remove("leaving");
      }, 450);
    }, 8000);
    locationMarker.hidden = true;
    targetCameraPosition = new THREE.Vector3(6.35, 4.15, 8.75);
    speak(
      "Welcome to the Oral Traditions Portal. You have arrived in the Kano Plains, where Luo oral tradition remembers Luanda Magere. Ask, and the guide will answer only from approved sources.",
    );
  };

  enterPortal.addEventListener("click", () => {
    enterPortal.disabled = true;
    enterPortal.classList.add("entering");
    journeyStartedAt = clock.getElapsedTime();
    locationMarker.hidden = false;
  });

  document.querySelector("#sunPosition").addEventListener("input", (event) => {
    updateSun(event.target.value);
  });
  document.querySelector("#moveSun").addEventListener("click", () => {
    sunPanel.hidden = !sunPanel.hidden;
  });
  toggleAmbienceButton.addEventListener("click", () => {
    if (ambienceContext) {
      stopAmbience();
    } else {
      startAmbience();
    }
  });
  document.querySelector("#toggleCaptions").addEventListener("click", () => {
    captionPanel.hidden = !captionPanel.hidden;
  });
  document.querySelector("#toggleSources").addEventListener("click", () => {
    sourcePanel.hidden = !sourcePanel.hidden;
  });
  toggleKeyboardButton.addEventListener("click", () => {
    legendChat.hidden = false;
    questionInput.focus();
  });
  document.querySelector("#closeSources").addEventListener("click", () => {
    sourcePanel.hidden = true;
  });

  const submitQuestion = async (question) => {
    const requestHistory = conversationHistory.slice(-6);
    addChatMessage("user", question);
    questionInput.value = "";
    voiceStatus.hidden = false;
    voiceStatus.textContent = "◌";
    guideSources.replaceChildren();
    try {
      const response = await fetch("/api/legends/luanda-magere/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          language: guideLanguage.value,
          history: requestHistory,
        }),
      });
      const result = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(result.detail)
          ? result.detail.map((item) => item.msg).filter(Boolean).join(" ")
          : result.detail;
        throw new Error(detail || "The guide could not answer.");
      }
      result.sources.forEach((source) => {
        const link = document.createElement("a");
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        link.textContent = source.organization;
        guideSources.append(link);
      });
      if (result.sources.length) {
        sourcePanel.classList.add("has-sources");
      }
      activeGuideGesture = result.gesture || "neutral";
      const spokenAnswer = result.follow_up
        ? `${result.answer} ${result.follow_up}`
        : result.answer;
      const generator = result.generator || "";
      const providerLabel = generator === "local-conversation"
        ? "Conversation"
        : generator === "verified-fallback"
          ? "Verified source response"
          : generator.toLowerCase().includes("gemma")
            ? "Generated by Gemma · approved sources"
            : generator.toLowerCase().includes("llama")
              ? "Generated by Llama · approved sources"
              : `Generated by ${generator} · approved sources`;
      addChatMessage("assistant", spokenAnswer, providerLabel);
      conversationHistory.push(
        { role: "user", content: question },
        { role: "assistant", content: spokenAnswer },
      );
      if (conversationHistory.length > 6) {
        conversationHistory.splice(0, conversationHistory.length - 6);
      }
      if (result.generation_warning) {
        addChatMessage("system", result.generation_warning);
      }
      speak(spokenAnswer, guideLanguage.value);
    } catch (error) {
      captionPanel.hidden = false;
      guideAnswer.textContent = error.message || "The guide could not answer that question.";
    } finally {
      voiceStatus.hidden = true;
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

  const stopVoiceStream = () => {
    if (voiceStream) {
      voiceStream.getTracks().forEach((track) => track.stop());
      voiceStream = null;
    }
  };

  const showVoiceMessage = (message) => {
    guideAnswer.textContent = message;
    captionPanel.hidden = false;
  };

  const transcribeVoiceQuestion = async (blob) => {
    voiceStatus.hidden = false;
    voiceStatus.textContent = "◌";
    showVoiceMessage("Transcribing your question… the first request can take up to a minute while Whisper starts.");
    const formData = new FormData();
    const extension = blob.type.includes("ogg") ? "ogg" : "webm";
    formData.append("audio", blob, `legend-question.${extension}`);
    formData.append("language", guideLanguage.value);
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 75000);

    try {
      const response = await fetch("/api/transcribe", {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || "The question could not be transcribed.");
      }
      const question = payload.text.trim();
      if (!question) {
        throw new Error("No speech was detected. Please move closer to the microphone and try again.");
      }
      questionInput.value = question;
      showVoiceMessage(`I heard: “${question}”`);
      await submitQuestion(question);
    } catch (error) {
      if (error.name === "AbortError") {
        showVoiceMessage("Transcription took too long. Please try a shorter question or use the keyboard.");
      } else {
        showVoiceMessage(error.message);
      }
    } finally {
      window.clearTimeout(timeout);
      voiceStatus.hidden = true;
    }
  };

  const stopVoiceQuestion = () => {
    window.clearTimeout(voiceStopTimer);
    if (voiceRecorder?.state === "recording") {
      voiceRecorder.stop();
    }
  };

  const beginVoiceQuestion = async () => {
    window.clearTimeout(voiceInvitationTimer);
    voiceInvitation.hidden = true;

    if (voiceRecorder?.state === "recording") {
      stopVoiceQuestion();
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      showVoiceMessage("Audio recording is unavailable in this browser.");
      return;
    }

    try {
      window.speechSynthesis?.cancel();
      stopNarration();
      guideSpeaking = false;
      let permissionTimedOut = false;
      showVoiceMessage("Waiting for microphone permission...");
      voiceStatus.hidden = false;
      voiceStatus.textContent = "●";
      const microphoneRequest = navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      microphoneRequest.then((stream) => {
        if (permissionTimedOut) {
          stream.getTracks().forEach((track) => track.stop());
        }
      });
      voiceStream = await Promise.race([
        microphoneRequest,
        new Promise((_, reject) => {
          window.setTimeout(() => {
            permissionTimedOut = true;
            const timeoutError = new Error("Microphone permission timed out.");
            timeoutError.name = "MicrophoneTimeoutError";
            reject(timeoutError);
          }, 7000);
        }),
      ]);
      if (permissionTimedOut) {
        stopVoiceStream();
        return;
      }
      voiceChunks = [];
      const options = { audioBitsPerSecond: 64000 };
      if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        options.mimeType = "audio/webm;codecs=opus";
      }
      voiceRecorder = new MediaRecorder(voiceStream, options);
      voiceRecorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) {
          voiceChunks.push(event.data);
        }
      });
      voiceRecorder.addEventListener("stop", () => {
        const blob = new Blob(voiceChunks, { type: voiceRecorder.mimeType });
        stopVoiceStream();
        voiceQuestionButton.classList.remove("listening");
        voiceStatus.hidden = true;
        if (performance.now() - voiceRecordingStartedAt < 700) {
          showVoiceMessage("That recording was too short. Hold the microphone for a moment, speak, then tap it again.");
          return;
        }
        transcribeVoiceQuestion(blob);
      }, { once: true });
      voiceRecorder.start();
      voiceRecordingStartedAt = performance.now();
      voiceQuestionButton.classList.add("listening");
      voiceStatus.hidden = false;
      voiceStatus.textContent = "●";
      showVoiceMessage("Listening... tap the microphone again when you finish.");
      voiceStopTimer = window.setTimeout(stopVoiceQuestion, 12000);
    } catch (error) {
      stopVoiceStream();
      voiceQuestionButton.classList.remove("listening");
      voiceStatus.hidden = true;
      if (error.name === "NotAllowedError") {
        showVoiceMessage("Microphone access was blocked. Allow microphone access in the browser and try again.");
      } else if (error.name === "NotFoundError") {
        showVoiceMessage("No microphone was found on this device.");
      } else if (error.name === "MicrophoneTimeoutError") {
        questionForm.hidden = false;
        showVoiceMessage("This preview did not open microphone permission. Use the keyboard box, or open the portal in Chrome or Edge to speak.");
      } else {
        showVoiceMessage(`The microphone could not start: ${error.message}`);
      }
    }
  };
  voiceQuestionButton.addEventListener("click", beginVoiceQuestion);
  voiceInvitation.addEventListener("click", beginVoiceQuestion);

  const resize = () => {
    const width = container.clientWidth;
    const height = container.clientHeight;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
  };
  window.addEventListener("resize", resize);

  const animate = (frameTime = 0) => {
    window.requestAnimationFrame(animate);
    if (document.hidden || frameTime - lastRenderedAt < 1000 / 30) {
      return;
    }
    lastRenderedAt = frameTime;
    const elapsed = clock.getElapsedTime();

    if (!landscapeActive) {
      earth.rotation.y += journeyStartedAt ? 0.004 : 0.0016;
      atmosphere.rotation.y -= 0.00045;
      stars.rotation.y += 0.00005;
      if (kenyaMarker) {
        const pulse = 1 + Math.sin(elapsed * 4.5) * 0.22;
        kenyaMarker.scale.setScalar(pulse);
      }

      if (journeyStartedAt !== null) {
        const progress = Math.min(1, (elapsed - journeyStartedAt) / (reducedMotion ? 1.1 : 4.8));
        const eased = 1 - Math.pow(1 - progress, 3);
        camera.position.z = THREE.MathUtils.lerp(8.2, 3.3, eased);
        camera.position.x = THREE.MathUtils.lerp(0, 0.65, eased);
        earth.rotation.y = THREE.MathUtils.lerp(earth.rotation.y, -0.67, 0.025);
        earth.rotation.x = THREE.MathUtils.lerp(earth.rotation.x, -0.02, 0.025);
        if (progress > 0.62) {
          cosmosGroup.scale.setScalar(1 + (progress - 0.62) * 1.8);
          earth.material.opacity = 1 - (progress - 0.62) / 0.38;
          earth.material.transparent = true;
          atmosphere.material.opacity = Math.max(0, 0.12 - (progress - 0.62) * 0.32);
        }
        if (progress >= 1) {
          enterPortal.hidden = true;
          enterLandscape();
        }
      }
    } else {
      if (!reducedMotion) {
        warrior.position.y = warriorBaseY;
        landscapeParticles.rotation.y += 0.0006;
        if (guideSpeaking) {
          chest.scale.y = 0.72 + Math.sin(elapsed * 7) * 0.025;
          head.rotation.y = Math.sin(elapsed * 2.8) * 0.06;
          if (loadedHeadBone) {
            loadedHeadBone.rotation.y = loadedHeadBaseRotationY + Math.sin(elapsed * 2.8) * 0.035;
          }
          if (loadedJawBone) {
            loadedJawBone.rotation.x = loadedJawBaseRotationX + Math.abs(Math.sin(elapsed * 8.5)) * 0.09;
          }
          const gesture = Math.sin(elapsed * 2.15);
          const counterGesture = Math.sin(elapsed * 1.65 + 1.7);
          const gestureStrength = {
            open_hands: 1.45,
            point_ground: 0.85,
            reflect: 0.55,
            neutral: 1,
          }[activeGuideGesture] || 1;
          const rightArmBias = activeGuideGesture === "point_ground" ? 0.08 : 0;
          [
            [loadedLeftUpperArm, gestureXAxis, gesture * 0.07 * gestureStrength],
            [loadedRightUpperArm, gestureXAxis, counterGesture * 0.09 * gestureStrength],
            [loadedLeftLowerArm, gestureZAxis, counterGesture * 0.045 * gestureStrength],
            [
              loadedRightLowerArm,
              gestureZAxis,
              gesture * -0.055 * gestureStrength - rightArmBias,
            ],
          ].forEach(([bone, axis, angle]) => {
            const baseQuaternion = armBaseQuaternions.get(bone);
            if (bone && baseQuaternion) {
              bone.quaternion
                .copy(baseQuaternion)
                .multiply(gestureQuaternion.setFromAxisAngle(axis, angle));
            }
          });
        } else {
          if (loadedHeadBone) {
            loadedHeadBone.rotation.y = THREE.MathUtils.lerp(
              loadedHeadBone.rotation.y,
              loadedHeadBaseRotationY,
              0.12,
            );
          }
          if (loadedJawBone) {
            loadedJawBone.rotation.x = THREE.MathUtils.lerp(
              loadedJawBone.rotation.x,
              loadedJawBaseRotationX,
              0.18,
            );
          }
          armBaseQuaternions.forEach((baseQuaternion, bone) => {
            bone.quaternion.slerp(baseQuaternion, 0.1);
          });
        }
      }
      if (targetCameraPosition) {
        camera.position.lerp(targetCameraPosition, 0.035);
        if (camera.position.distanceTo(targetCameraPosition) < 0.06) {
          targetCameraPosition = null;
        }
      }
      controls.update();
    }
    renderer.render(scene, camera);
    renderer.render(scene, camera);
  };

  document.querySelector("#sceneLoading").hidden = true;
  animate();
}
