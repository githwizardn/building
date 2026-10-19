import * as THREE from "three";

export function create2RoomApartment() {
  const group = new THREE.Group();
  group.name = "Apartment_2_Rooms";

  const wallHeight = 2.5; 
  const wallThick = 0.15;
  
  const wallMat = new THREE.MeshStandardMaterial({ color: 0xeeeeee, roughness: 0.9 });
  const glassMat = new THREE.MeshStandardMaterial({ color: 0xaaccff, transparent: true, opacity: 0.4, roughness: 0.1 });
  const doorMat = new THREE.MeshStandardMaterial({ color: 0x8b5a2b, roughness: 0.7 });


  function addWall(cx, cz, angleDeg, length, width) {
    const angle = angleDeg * Math.PI / 180;
    const geo = new THREE.BoxGeometry(length, wallHeight, width);
    const wall = new THREE.Mesh(geo, wallMat);
    wall.position.set(cx, wallHeight / 2, cz);
    wall.rotation.y = -angle; 
    wall.castShadow = true;
    wall.receiveShadow = true;
    group.add(wall);
  }

 const walls = [
    [1.18, -0.079, 180, 2.502, 0.075],
    [-0.1, 6.822, 90, 2.148, 0.15],
    [3.816, 2.15, 180, 1.537, 0.15],
    [2.554, 1.036, 270, 2.228, 0.15],
    [4.592, 3.949, 269.7, 3.673, 0.075],
    [1.497, 2.15, 0, 3.1, 0.15],
    [4.05, 5.747, 0, 1.175, 0.075],
    [-0.053, 1.036, 90, 2.303, 0.15],
    [0.174, 7.971, 0, 8.861, 0.15],
    [4.471, -2, 180, 3.852, 0.075],
    [5.517, 2.157, 0.46, 1.867, 0.15],
    [2.548, -1.039, 90, 1.997, 0.15],
    [4.975, 7.933, 358.5, 2.952, 0.15],
    [-0.1, 4.935, 270, 1.624, 0.15],
    [1.7, 5.747, 0, 3.6, 0.075],
    [-4.179, 6.047, 90, 4.074, 0.075],
    [3.5, 6.859, 270, 2.224, 0.075],
    [-2.185, 4.123, 180, 4.266, 0.075],
    [-0.076, 3.137, 91.36, 1.974, 0.15],
    [7.439, 2.157, 179.5, 2.054, 0.15],
    [6.45, 0.082, 270, 4.239, 0.15],
    [7.439, 7.896, 0.01, 2.053, 0.15],
    [7.439, 4.582, 359.5, 2.128, 0.075],
    [8.427, 3.362, 270, 2.575, 0.075],
    [6.45, 3.377, 90, 2.502, 0.15],
    [7.439, 5.747, 0, 2.128, 0.075],
    [6.45, 6.822, 90, 2.223, 0.15],
    [8.427, 6.822, 270, 2.298, 0.075],
    [8.427, 5.161, 270, 1.174, 0.075]
  ];
  walls.forEach(w => addWall(w[0], w[1], w[2], w[3], w[4]));

  function addDoor(cx, cz, angleDeg, width) {
    const height = 2.1;
    const geo = new THREE.BoxGeometry(width, height, wallThick * 1.5);
    const door = new THREE.Mesh(geo, doorMat);
    door.position.set(cx, height / 2, cz);
    door.rotation.y = -(angleDeg * Math.PI / 180); 
    door.castShadow = true;
    group.add(door);
  }
  addDoor(5.757, 2.159, 180.46, 0.9);
  addDoor(4.063, 5.747, 0, 0.9);
  addDoor(7.123, 4.585, 359.54, 0.9);
  addDoor(7.121, 5.747, 180, 0.9);
  addDoor(3.5, 6.327, 270, 0.9);
  addDoor(5.95, 7.909, 358.5, 0.9);
  addDoor(-0.1, 6.389, 270, 0.9);

  function addWindow(cx, cz, angleDeg, width) {
    const sillHeight = 0.9;
    const winHeight = 1.2;
    const topHeight = wallHeight - sillHeight - winHeight;

    const geo1 = new THREE.BoxGeometry(width, sillHeight, wallThick);
    const sill = new THREE.Mesh(geo1, wallMat);
    sill.position.set(cx, sillHeight / 2, cz);
    sill.rotation.y = -(angleDeg * Math.PI / 180);
    group.add(sill);

    const geo2 = new THREE.BoxGeometry(width, topHeight, wallThick);
    const top = new THREE.Mesh(geo2, wallMat);
    top.position.set(cx, sillHeight + winHeight + topHeight / 2, cz);
    top.rotation.y = -(angleDeg * Math.PI / 180);
    group.add(top);

    const geo3 = new THREE.BoxGeometry(width, winHeight, wallThick * 0.2);
    const glass = new THREE.Mesh(geo3, glassMat);
    glass.position.set(cx, sillHeight + winHeight / 2, cz);
    glass.rotation.y = -(angleDeg * Math.PI / 180);
    group.add(glass);
  }
  addWindow(-1.166, 4.123, 180, 1.3);
  addWindow(-0.084, 3.455, 91.36, 1.0);
  addWindow(1.372, -0.079, 180, 1.3);
  addWindow(4.605, -2, 180, 0.87);

  return group;
}