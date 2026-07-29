local UEHelpers = require("UEHelpers")

local MOD_NAME = "PalCompanionUI"
local COMPANION_URL = "http://127.0.0.1:8765/?client=ue4ss"
local DEFAULT_MARKER_ICON_TYPE = 0
local browser_widget = nil
local root_widget = nil
local visible = false
local last_marker_command = nil
local last_close_command = nil
local last_storage_command = nil
local input_captured = false
local previous_move_input_ignored = false
local previous_look_input_ignored = false
local storage_cache = {}
local MAX_STORAGE_CONTAINERS = 32
local MAX_STORAGE_STACKS = 512
local MAX_STORAGE_MOVES = 32

local function log(message)
    print(string.format("[%s] %s\n", MOD_NAME, message))
end

local function valid(object)
    return object and object:IsValid()
end

local function find_class(path)
    local class = StaticFindObject(path)
    if not valid(class) then
        error("Missing Unreal class: " .. path)
    end
    return class
end

local function create_object(class_path, outer)
    local class = find_class(class_path)
    local object = StaticConstructObject(class, outer, 0, 0, 0, nil, false, false, nil)
    if not valid(object) then
        error("Could not construct: " .. class_path)
    end
    return object
end

local function url_encode(value)
    return tostring(value):gsub("([^%w%-_%.~])", function(character)
        return string.format("%%%02X", string.byte(character))
    end)
end

local function json_escape(value)
    return tostring(value or "")
        :gsub("\\", "\\\\")
        :gsub('"', '\\"')
        :gsub("\b", "\\b")
        :gsub("\f", "\\f")
        :gsub("\n", "\\n")
        :gsub("\r", "\\r")
        :gsub("\t", "\\t")
end

local function string_value(value)
    if value == nil then
        return ""
    end
    local ok, converted = pcall(function()
        return value:ToString()
    end)
    if ok and converted then
        return tostring(converted)
    end
    return tostring(value)
end

local function guid_key(guid)
    if not guid then
        return nil
    end
    local ok, key = pcall(function()
        local function uint32(value)
            return value < 0 and value + 4294967296 or value
        end
        return string.format(
            "%08x%08x%08x%08x",
            uint32(guid.A),
            uint32(guid.B),
            uint32(guid.C),
            uint32(guid.D)
        )
    end)
    if not ok then
        return nil
    end
    return key
end

local function companion_url(controller)
    local player_state = controller.PlayerState
    if not valid(player_state) then
        return COMPANION_URL
    end
    local ok, player_name = pcall(function()
        return player_state:GetPlayerName()
    end)
    if not ok or not player_name then
        return COMPANION_URL
    end
    local value_ok, player_name_value = pcall(function()
        return player_name:ToString()
    end)
    if not value_ok or not player_name_value or player_name_value == "" then
        return COMPANION_URL
    end
    return COMPANION_URL .. "&player=" .. url_encode(player_name_value)
end

local function set_game_input(controller)
    controller.bShowMouseCursor = false
    pcall(function()
        controller:SetIgnoreMoveInput(previous_move_input_ignored)
        controller:SetIgnoreLookInput(previous_look_input_ignored)
    end)
    input_captured = false
    local input_library = StaticFindObject(
        "/Script/UMG.Default__WidgetBlueprintLibrary"
    )
    if valid(input_library) then
        input_library:SetInputMode_GameOnly(controller, true)
    end
end

local function set_ui_input(controller, widget)
    if not input_captured then
        local move_ok, move_ignored = pcall(function()
            return controller:IsMoveInputIgnored()
        end)
        local look_ok, look_ignored = pcall(function()
            return controller:IsLookInputIgnored()
        end)
        previous_move_input_ignored = move_ok and move_ignored or false
        previous_look_input_ignored = look_ok and look_ignored or false
        input_captured = true
    end

    controller.bShowMouseCursor = true
    pcall(function()
        controller:SetIgnoreMoveInput(true)
        controller:SetIgnoreLookInput(true)
    end)
    local input_library = StaticFindObject(
        "/Script/UMG.Default__WidgetBlueprintLibrary"
    )
    if valid(input_library) then
        local mode_ok, mode_error = pcall(function()
            input_library:SetInputMode_UIOnlyEx(
                controller,
                browser_widget or widget,
                0,
                true
            )
        end)
        if not mode_ok then
            log("UI-only mode unavailable; using locked Game+UI mode: " .. tostring(mode_error))
            input_library:SetInputMode_GameAndUIEx(
                controller,
                browser_widget or widget,
                0,
                false,
                true
            )
        end
    end
    if valid(browser_widget) then
        pcall(function()
            browser_widget:SetKeyboardFocus()
        end)
    end
end

local function map_to_world(map_x, map_y)
    local world_x = (map_y * 460.0) - 123000.0
    local world_y = (map_x * 460.0) + 158000.0
    return world_x, world_y
end

local function add_map_marker(map_x, map_y, icon_type)
    local controller = UEHelpers:GetPlayerController()
    if not valid(controller) then
        error("PlayerController is not ready")
    end

    local utility = StaticFindObject("/Script/Pal.Default__PalUtility")
    if not valid(utility) then
        error("PalUtility is unavailable")
    end

    local location_manager = utility:GetLocationManager(controller)
    if not valid(location_manager) then
        error("PalLocationManager is unavailable")
    end

    local world_x, world_y = map_to_world(map_x, map_y)
    local marker_icon_type = tonumber(icon_type) or DEFAULT_MARKER_ICON_TYPE
    marker_icon_type = math.max(0, math.min(13, math.floor(marker_icon_type)))
    location_manager:AddLocalCustomMarker(
        {X = world_x, Y = world_y, Z = 0.0},
        marker_icon_type
    )
    log(string.format(
        "Placed map marker at %.1f, %.1f with icon %d",
        map_x,
        map_y,
        marker_icon_type
    ))
end

local function acknowledge_marker_placement(count)
    if count < 1 or not valid(browser_widget) then
        return
    end
    local script = string.format(
        "window.palCompanionMarkerPlaced && window.palCompanionMarkerPlaced(%d);",
        count
    )
    local ok, message = pcall(function()
        browser_widget:ExecuteJavascript(script)
    end)
    if not ok then
        log("Could not acknowledge marker placement: " .. tostring(message))
    end
end

local function execute_browser_script(script)
    if not valid(browser_widget) then
        return false
    end
    local ok, message = pcall(function()
        browser_widget:ExecuteJavascript(script)
    end)
    if not ok then
        log("Browser callback failed: " .. tostring(message))
    end
    return ok
end

local function storage_owner_key(model)
    if not valid(model) then
        return nil
    end
    local ok, owner_id = pcall(function()
        local actor = model:GetActor()
        if not valid(actor) then
            return nil
        end
        local map_model = actor:GetModel()
        if not valid(map_model) then
            return nil
        end
        return guid_key(map_model:GetBuildPlayerUId_BP())
    end)
    if not ok then
        return nil
    end
    return owner_id
end

local function storage_scan_json()
    local controller = UEHelpers:GetPlayerController()
    if not valid(controller) then
        error("PlayerController is not ready")
    end
    local player_id = guid_key(controller:GetPlayerUId())
    if not player_id or player_id == string.rep("0", 32) then
        error("Current player ownership ID is unavailable")
    end
    local storage_class = StaticFindObject("/Script/Pal.PalMapObjectItemStorageModel")
    if not valid(storage_class) then
        error("PalMapObjectItemStorageModel is unavailable")
    end

    local models = FindAllOf("PalMapObjectConcreteModelBase") or {}
    local containers = {}
    local next_cache = {}
    local total_stacks = 0
    local excluded_containers = 0
    for _, model in ipairs(models) do
        if #containers >= MAX_STORAGE_CONTAINERS or total_stacks >= MAX_STORAGE_STACKS then
            break
        end
        local model_ok, is_storage = pcall(function()
            return valid(model) and model:IsA(storage_class)
        end)
        if model_ok and is_storage then
            local owner_id = storage_owner_key(model)
            if owner_id ~= player_id then
                excluded_containers = excluded_containers + 1
            else
                local ok, snapshot = pcall(function()
                local module = model:GetItemContainerModule()
                if not valid(module) then
                    return nil
                end
                local container = module:GetContainer()
                if not valid(container) then
                    return nil
                end
                local container_id = guid_key(container:GetId().ID)
                local model_id = guid_key(model:GetModelInstanceId())
                local base_id = guid_key(model:GetBaseCampIdBelongTo())
                if not container_id or not model_id or not base_id then
                    return nil
                end

                local label = string_value(model:TryGetItemContainerOverrideName())
                label = label:gsub("^%s+", ""):gsub("%s+$", "")
                local transform = model:GetTransform()
                local location = transform and transform.Translation or nil
                local items = {}
                local slot_count = math.min(container:Num(), 128)
                for index = 0, slot_count - 1 do
                    if total_stacks + #items >= MAX_STORAGE_STACKS then
                        break
                    end
                    local slot = container:Get(index)
                    if valid(slot) and not slot:IsEmpty() then
                        local item_id = slot:GetItemId()
                        local static_id = string_value(item_id.StaticId)
                        local count = slot:GetStackCount()
                        if static_id ~= "" and count > 0 then
                            table.insert(items, {
                                item_id = static_id,
                                slot_index = index,
                                count = count
                            })
                        end
                    end
                end
                return {
                    container_id = container_id,
                    model_id = model_id,
                    base_id = base_id,
                    owner_player_id = owner_id,
                    label = label,
                    x = location and location.X or 0.0,
                    y = location and location.Y or 0.0,
                    z = location and location.Z or 0.0,
                    items = items,
                    container = container,
                    model = model
                }
                end)
                if ok and snapshot then
                    next_cache[snapshot.container_id] = snapshot
                    total_stacks = total_stacks + #snapshot.items
                    table.insert(containers, snapshot)
                end
            end
        end
    end

    storage_cache = next_cache
    local encoded = {string.format(
        '{"player_id":"%s","excluded_container_count":%d,"containers":[',
        player_id,
        excluded_containers
    )}
    for index, container in ipairs(containers) do
        if index > 1 then
            table.insert(encoded, ",")
        end
        table.insert(encoded, string.format(
            '{"container_id":"%s","model_id":"%s","base_id":"%s",' ..
            '"owner_player_id":"%s",' ..
            '"label":"%s","x":%.2f,"y":%.2f,"z":%.2f,"items":[',
            container.container_id,
            container.model_id,
            container.base_id,
            container.owner_player_id,
            json_escape(container.label),
            container.x,
            container.y,
            container.z
        ))
        for item_index, item in ipairs(container.items) do
            if item_index > 1 then
                table.insert(encoded, ",")
            end
            table.insert(encoded, string.format(
                '{"item_id":"%s","display_name":"%s","slot_index":%d,"count":%d}',
                json_escape(item.item_id),
                json_escape(item.item_id),
                item.slot_index,
                item.count
            ))
        end
        table.insert(encoded, "]}")
    end
    table.insert(encoded, "]}")
    log(string.format(
        "Storage scan found %d owned chest(s), excluded %d other chest(s), and %d occupied stack(s)",
        #containers,
        excluded_containers,
        total_stacks
    ))
    return table.concat(encoded)
end

local function send_storage_snapshot()
    local ok, payload = pcall(storage_scan_json)
    if not ok then
        execute_browser_script(string.format(
            "window.palCompanionStorageError && " ..
            "window.palCompanionStorageError(\"%s\");",
            json_escape(payload)
        ))
        log("Storage scan failed: " .. tostring(payload))
        return
    end
    execute_browser_script(
        "window.palCompanionStorageSnapshot && " ..
        "window.palCompanionStorageSnapshot(" .. payload .. ");"
    )
end

local function request_storage_moves(payload)
    local controller = UEHelpers:GetPlayerController()
    if not valid(controller) then
        error("PlayerController is not ready")
    end
    local utility = StaticFindObject("/Script/Pal.Default__PalUtility")
    local guid_library = StaticFindObject("/Script/Engine.Default__KismetGuidLibrary")
    if not valid(utility) or not valid(guid_library) then
        error("Palworld storage networking is unavailable")
    end
    local transmitter = utility:GetNetworkTransmitter(controller)
    if not valid(transmitter) then
        error("Local network transmitter is unavailable")
    end
    local network_item = transmitter:GetItem()
    if not valid(network_item) then
        error("Local item network component is unavailable")
    end
    local player_id = guid_key(controller:GetPlayerUId())
    if not player_id or player_id == string.rep("0", 32) then
        error("Current player ownership ID is unavailable")
    end

    local submitted = 0
    local rejected = 0
    local target_count = 0
    for target_group in payload:gmatch("[^;]+") do
        if submitted >= MAX_STORAGE_MOVES then
            break
        end
        local segments = {}
        for segment in target_group:gmatch("[^~]+") do
            table.insert(segments, segment)
        end
        local target = storage_cache[segments[1] or ""]
        local froms = {}
        if not target
            or target.label == ""
            or target.owner_player_id ~= player_id
            or storage_owner_key(target.model) ~= player_id
            or not valid(target.container) then
            rejected = rejected + math.max(1, #segments - 1)
        else
            for index = 2, #segments do
                if submitted + #froms >= MAX_STORAGE_MOVES then
                    break
                end
                local source_id, slot_index_text, count_text = segments[index]:match(
                    "^([0-9a-f]+),(%d+),(%d+)$"
                )
                local source = source_id and storage_cache[source_id] or nil
                local slot_index = tonumber(slot_index_text)
                local requested_count = tonumber(count_text)
                local accepted = source
                    and source.label ~= ""
                    and source.owner_player_id == player_id
                    and storage_owner_key(source.model) == player_id
                    and source.base_id == target.base_id
                    and valid(source.container)
                    and slot_index
                    and requested_count
                    and slot_index >= 0
                    and requested_count > 0
                if accepted then
                    local slot = source.container:Get(slot_index)
                    local scanned_item = nil
                    for _, item in ipairs(source.items) do
                        if item.slot_index == slot_index then
                            scanned_item = item
                            break
                        end
                    end
                    accepted = valid(slot)
                        and not slot:IsEmpty()
                        and scanned_item
                        and string_value(slot:GetItemId().StaticId) == scanned_item.item_id
                        and slot:GetStackCount() >= requested_count
                    if accepted then
                        table.insert(froms, {
                            SlotId = slot:GetSlotId(),
                            Num = requested_count
                        })
                    end
                end
                if not accepted then
                    rejected = rejected + 1
                end
            end
            if #froms > 0 then
                network_item:RequestMoveToContainer_ToServer(
                    guid_library:NewGuid(),
                    target.container:GetId(),
                    froms
                )
                submitted = submitted + #froms
                target_count = target_count + 1
            end
        end
    end
    log(string.format(
        "Storage organizer submitted %d move(s) to %d chest(s); %d rejected",
        submitted,
        target_count,
        rejected
    ))
    execute_browser_script(string.format(
        "window.palCompanionStorageSubmitted && " ..
        "window.palCompanionStorageSubmitted(%d,%d);",
        submitted,
        rejected
    ))
end

local function process_storage_command(command)
    local _, action, payload = command:match("^([^;]+);([^;]+);?(.*)$")
    ExecuteInGameThread(function()
        if action == "scan" then
            send_storage_snapshot()
            return
        end
        if action == "execute" and payload and payload ~= "" then
            local ok, message = pcall(request_storage_moves, payload)
            if not ok then
                execute_browser_script(string.format(
                    "window.palCompanionStorageError && " ..
                    "window.palCompanionStorageError(\"%s\");",
                    json_escape(message)
                ))
                log("Storage apply failed: " .. tostring(message))
            end
        end
    end)
end

local function process_marker_command(command)
    local payload = command:match("^[^;]+;(.+)$")
    if not payload then
        log("Ignored malformed marker command")
        return
    end

    local coordinates = {}
    for pair in payload:gmatch("[^;]+") do
        local x, y, icon_type = pair:match(
            "^(-?[%d%.]+),(-?[%d%.]+),?(%d*)$"
        )
        if x and y then
            table.insert(coordinates, {
                x = tonumber(x),
                y = tonumber(y),
                icon_type = tonumber(icon_type) or DEFAULT_MARKER_ICON_TYPE
            })
        end
        if #coordinates >= 12 then
            break
        end
    end

    if #coordinates == 0 then
        log("Marker command contained no valid coordinates")
        return
    end

    ExecuteInGameThread(function()
        local placed = 0
        for _, coordinate in ipairs(coordinates) do
            local ok, message = pcall(
                add_map_marker,
                coordinate.x,
                coordinate.y,
                coordinate.icon_type
            )
            if ok then
                placed = placed + 1
            else
                log("Map marker failed: " .. tostring(message))
            end
        end
        acknowledge_marker_placement(placed)
    end)
end

local function build_overlay(initial_url)
    local controller = UEHelpers:GetPlayerController()
    if not valid(controller) then
        error("PlayerController is not ready")
    end

    root_widget = create_object("/Script/UMG.UserWidget", controller)
    local widget_tree = create_object("/Script/UMG.WidgetTree", root_widget)
    local canvas = create_object("/Script/UMG.CanvasPanel", widget_tree)
    browser_widget = create_object(
        "/Script/WebBrowserWidget.WebBrowser",
        widget_tree
    )

    root_widget.WidgetTree = widget_tree
    widget_tree.RootWidget = canvas
    local url = initial_url or companion_url(controller)
    browser_widget.InitialURL = url
    browser_widget.bSupportsTransparency = true

    local slot = canvas:AddChildToCanvas(browser_widget)
    slot:SetAnchors({
        Minimum = {X = 0.10, Y = 0.08},
        Maximum = {X = 0.90, Y = 0.92}
    })
    slot:SetOffsets({Left = 0, Top = 0, Right = 0, Bottom = 0})
    slot:SetAlignment({X = 0.5, Y = 0.5})

    root_widget:AddToViewport(9000)
    browser_widget:LoadURL(url)
    root_widget:SetVisibility(1)
    visible = false
    log("Overlay created")
end

local function show_overlay(controller, url)
    if not valid(root_widget) or not valid(browser_widget) then
        build_overlay(url)
    else
        browser_widget:LoadURL(url)
    end
    visible = true
    root_widget:SetVisibility(0)
    set_ui_input(controller, root_widget)
end

local function toggle_overlay()
    ExecuteInGameThread(function()
        local controller = UEHelpers:GetPlayerController()
        if not valid(controller) then
            log("PlayerController is not ready")
            return
        end

        if not valid(root_widget) or not valid(browser_widget) then
            local ok, message = pcall(build_overlay)
            if not ok then
                log("Overlay creation failed: " .. tostring(message))
                return
            end
        end

        visible = not visible
        root_widget:SetVisibility(visible and 0 or 1)
        if visible then
            browser_widget:LoadURL(companion_url(controller))
            set_ui_input(controller, root_widget)
            log("Overlay opened")
        else
            set_game_input(controller)
            log("Overlay closed")
        end
    end)
end

local function open_vendor_directory()
    ExecuteInGameThread(function()
        local controller = UEHelpers:GetPlayerController()
        if not valid(controller) then
            log("PlayerController is not ready")
            return
        end

        local url = companion_url(controller) .. "&view=vendors"
        local ok, message = pcall(show_overlay, controller, url)
        if not ok then
            log("Vendor directory failed: " .. tostring(message))
            return
        end
        log("Vendor directory opened")
    end)
end

local function open_storage_organizer()
    ExecuteInGameThread(function()
        local controller = UEHelpers:GetPlayerController()
        if not valid(controller) then
            log("PlayerController is not ready")
            return
        end

        local url = companion_url(controller) .. "&view=organizer"
        local ok, message = pcall(show_overlay, controller, url)
        if not ok then
            log("Storage organizer failed: " .. tostring(message))
            return
        end
        log("Storage organizer opened")
    end)
end

local function open_admin_supplies()
    ExecuteInGameThread(function()
        local controller = UEHelpers:GetPlayerController()
        if not valid(controller) then
            log("PlayerController is not ready")
            return
        end

        local url = companion_url(controller) .. "&view=supplies"
        local ok, message = pcall(show_overlay, controller, url)
        if not ok then
            log("Admin Supplies failed: " .. tostring(message))
            return
        end
        log("Private Admin Supplies opened")
    end)
end

local function close_overlay()
    local controller = UEHelpers:GetPlayerController()
    if not valid(controller) then
        return
    end
    visible = false
    if valid(root_widget) then
        root_widget:SetVisibility(1)
    end
    set_game_input(controller)
    log("Overlay closed")
end

RegisterKeyBind(Key.F2, toggle_overlay)
RegisterKeyBind(Key.F3, open_vendor_directory)
RegisterKeyBind(Key.F4, open_storage_organizer)
RegisterKeyBind(Key.F5, open_admin_supplies)

LoopAsync(250, function()
    if not valid(browser_widget) then
        return false
    end

    local ok, url = pcall(function()
        return browser_widget:GetUrl()
    end)
    if not ok or not url then
        return false
    end

    local command = tostring(url):match("#palmarkers=([^#]+)")
    if command and command ~= last_marker_command then
        last_marker_command = command
        process_marker_command(command)
    end
    local close_command = tostring(url):match("#palclose=([^#]+)")
    if close_command and close_command ~= last_close_command then
        last_close_command = close_command
        ExecuteInGameThread(function()
            close_overlay()
        end)
    end
    local storage_command = tostring(url):match("#palstorage=([^#]+)")
    if storage_command and storage_command ~= last_storage_command then
        last_storage_command = storage_command
        process_storage_command(storage_command)
    end
    return false
end)

log("Loaded. F2 companion, F3 vendors, F4 storage organizer, F5 private supplies.")
