// server.js — Node.js + Socket.IO сервер для Lunar Odyssey
const express = require('express');
const { createServer } = require('http');
const { Server } = require('socket.io');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

// Health check endpoint для Render
app.get('/', (req, res) => {
  res.json({ 
    status: 'ok', 
    service: 'Lunar Odyssey Multiplayer',
    players: players.size,
    timestamp: new Date().toISOString()
  });
});

const httpServer = createServer(app);

const io = new Server(httpServer, {
  cors: {
    origin: '*', // В продакшене замените на домен вашего VK Mini App
    methods: ['GET', 'POST']
  },
  // Настройки для стабильности на Render
  pingTimeout: 60000,
  pingInterval: 25000
});

// Хранилище игроков: socketId -> { position, rotation, name, color }
const players = new Map();

// ====== ПОДКЛЮЧЕНИЕ ИГРОКА ======
io.on('connection', (socket) => {
  console.log(`[+] Player connected: ${socket.id}`);

  // Новый игрок: создаём запись со спавном в случайной точке
  const spawnX = (Math.random() - 0.5) * 1000;
  const spawnZ = (Math.random() - 0.5) * 1000;

  players.set(socket.id, {
    id: socket.id,
    position: { x: spawnX, y: 0, z: spawnZ },
    rotation: { yaw: 0, pitch: 0 },
    name: `Космонавт-${socket.id.slice(0, 4)}`,
    color: Math.floor(Math.random() * 0xffffff)
  });

  // Отправляем новому игроку список уже подключённых
  const existingPlayers = Array.from(players.values()).filter(p => p.id !== socket.id);
  socket.emit('init', { 
    yourId: socket.id, 
    players: existingPlayers,
    spawnPosition: { x: spawnX, y: 0, z: spawnZ }
  });

  // Сообщаем всем остальным о новом игроке
  socket.broadcast.emit('playerJoined', players.get(socket.id));

  // ====== СИНХРОНИЗАЦИЯ ПОЗИЦИЙ ======
  // Клиент отправляет свою позицию ~20 раз в секунду
  socket.on('positionUpdate', (data) => {
    const player = players.get(socket.id);
    if (!player) return;

    player.position = data.position;
    player.rotation = data.rotation;

    // Рассылаем всем остальным (не себе)
    socket.broadcast.emit('playerMoved', {
      id: socket.id,
      position: data.position,
      rotation: data.rotation
    });
  });

  // ====== WEBRTC СИГНАЛИНГ ДЛЯ АУДИОСВЯЗИ ======
  // WebRTC offer — инициатор звонка отправляет SDP другому игроку
  socket.on('webrtc-offer', ({ targetId, offer }) => {
    io.to(targetId).emit('webrtc-offer', {
      fromId: socket.id,
      offer
    });
  });

  // WebRTC answer — получатель отвечает
  socket.on('webrtc-answer', ({ targetId, answer }) => {
    io.to(targetId).emit('webrtc-answer', {
      fromId: socket.id,
      answer
    });
  });

  // ICE candidates — для обхода NAT
  socket.on('webrtc-ice-candidate', ({ targetId, candidate }) => {
    io.to(targetId).emit('webrtc-ice-candidate', {
      fromId: socket.id,
      candidate
    });
  });

  // ====== ОТКЛЮЧЕНИЕ ======
  socket.on('disconnect', () => {
    console.log(`[-] Player disconnected: ${socket.id}`);
    players.delete(socket.id);
    io.emit('playerLeft', socket.id);
  });
});

// ====== ЗАПУСК СЕРВЕРА ======
const PORT = process.env.PORT || 3000;
httpServer.listen(PORT, () => {
  console.log(`🛰️  Lunar Odyssey server running on port ${PORT}`);
  console.log(`   WebSocket ready at ws://localhost:${PORT}`);
});
