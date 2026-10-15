-- ===========================================================================================
--  CS1-to-BeamNG :: level load verification probe
-- ===========================================================================================
--  Dropped into the BeamNG user folder by the converter's test harness and run with:
--
--      BeamNG.drive.x64.exe -level Cannes -lua "require('cs1_verify')"
--
--  It waits for the level to finish loading, then reports what the engine actually built from
--  the generated files.  This is the difference between "the JSON is well formed" and "BeamNG
--  loaded it": a malformed terrain or a rejected items.level.json shows up here and nowhere
--  else.
--
--  Results are written to the normal log and also to cs1_verify_result.json in the user folder
--  so the harness can read them back without parsing the log.
-- ===========================================================================================

local M = {}

local RESULT_PATH = 'cs1_verify_result.json'
local done = false

local function safeCount(list)
  local count = 0
  pcall(function()
    for _ in pairs(list) do
      count = count + 1
    end
  end)
  return count
end

-- Recursively walk the scene graph counting object classes.
local function walk(node, counts, depth)
  if node == nil or depth > 12 then
    return
  end

  local class = nil
  pcall(function() class = node:getClassName() end)
  if class then
    counts[class] = (counts[class] or 0) + 1
  end

  local children = nil
  pcall(function() children = node:getChildren() end)
  if children then
    local ok = pcall(function()
      for child in children do
        walk(child, counts, depth + 1)
      end
    end)
    if not ok then
      -- getChildren() may not be iterable in every build; fall back to counting only.
    end
  end
end

local function report()
  if done then
    return
  end
  done = true

  local result = {
    levelName = nil,
    terrainFound = false,
    terrainFile = nil,
    terrainSize = nil,
    decalRoads = 0,
    statics = 0,
    spawnPoints = 0,
    errors = {},
  }

  pcall(function()
    result.levelName = getMissionFilename and getMissionFilename() or nil
  end)

  -- The TerrainBlock and the terrain it instantiated.
  pcall(function()
    local terrain = scenetree.findClassObjects and scenetree.findClassObjects('TerrainBlock') or {}
    local first = nil
    for _, obj in pairs(terrain) do
      first = obj
      break
    end
    if first then
      result.terrainFound = true
      pcall(function() result.terrainFile = first.terrainFile end)
      pcall(function()
        if first.getTerrainTextureSize then
          result.terrainSize = first:getTerrainTextureSize()
        end
      end)
      pcall(function()
        if first.getTerrainSize then
          result.terrainSize = first:getTerrainSize()
        end
      end)
    end
  end)

  pcall(function()
    local roads = scenetree.findClassObjects and scenetree.findClassObjects('DecalRoad') or {}
    result.decalRoads = safeCount(roads)
  end)

  pcall(function()
    local statics = scenetree.findClassObjects and scenetree.findClassObjects('TSStatic') or {}
    result.statics = safeCount(statics)
  end)

  pcall(function()
    local spawns = scenetree.findClassObjects and scenetree.findClassObjects('SpawnSphere') or {}
    result.spawnPoints = safeCount(spawns)
  end)

  log('I', 'cs1_verify', '=== CS1-to-BeamNG level verification ===')
  log('I', 'cs1_verify', 'level filename  : ' .. tostring(result.levelName))
  log('I', 'cs1_verify', 'TerrainBlock    : ' .. tostring(result.terrainFound))
  log('I', 'cs1_verify', 'terrainFile     : ' .. tostring(result.terrainFile))
  log('I', 'cs1_verify', 'terrain size    : ' .. tostring(result.terrainSize))
  log('I', 'cs1_verify', 'DecalRoads      : ' .. tostring(result.decalRoads))
  log('I', 'cs1_verify', 'TSStatic        : ' .. tostring(result.statics))
  log('I', 'cs1_verify', 'SpawnSpheres    : ' .. tostring(result.spawnPoints))

  pcall(function()
    local handle = io.open(RESULT_PATH, 'w')
    if handle then
      handle:write(string.format(
        '{"levelName":"%s","terrainFound":%s,"terrainFile":"%s","terrainSize":"%s",' ..
        '"decalRoads":%d,"statics":%d,"spawnPoints":%d}\n',
        tostring(result.levelName), tostring(result.terrainFound),
        tostring(result.terrainFile), tostring(result.terrainSize),
        result.decalRoads, result.statics, result.spawnPoints))
      handle:close()
    end
  end)

  log('I', 'cs1_verify', '=== verification complete ===')
end

-- Poll until the level reports itself loaded, then report once.
M.onClientPostStartMission = function()
  log('I', 'cs1_verify', 'onClientPostStartMission received')
  report()
end

M.onUpdate = function(dt)
  if done then
    return
  end
  -- Fallback: if the mission callback never fires, report anyway after the world exists.
  local ok, loaded = pcall(function()
    return scenetree and scenetree.findClassObjects ~= nil
  end)
  if ok and loaded then
    local terrain = nil
    pcall(function()
      terrain = scenetree.findClassObjects('TerrainBlock')
    end)
    if terrain then
      for _, obj in pairs(terrain) do
        if obj then
          report()
          return
        end
      end
    end
  end
end

-- Register as an extension so the callbacks above are driven by the engine.
local function onExtensionLoaded()
  log('I', 'cs1_verify', 'probe extension loaded')
end

return M
