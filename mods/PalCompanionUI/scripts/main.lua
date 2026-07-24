local UEHelpers = require("UEHelpers")

local MOD_NAME = "PalCompanionUI"
local COMPANION_URL = "http://127.0.0.1:8765/?client=ue4ss"
local MARKER_ICON_TYPE = 0
local browser_widget = nil
local root_widget = nil
local visible = false
local last_marker_command = nil

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

local function set_game_input(controller)
    controller.bShowMouseCursor = false
    local input_library = StaticFindObject(
        "/Script/UMG.Default__WidgetBlueprintLibrary"
    )
    if valid(input_library) then
        input_library:SetInputMode_GameOnly(controller, false)
    end
end

local function set_ui_input(controller, widget)
    controller.bShowMouseCursor = true
    local input_library = StaticFindObject(
        "/Script/UMG.Default__WidgetBlueprintLibrary"
    )
    if valid(input_library) then
        input_library:SetInputMode_GameAndUIEx(
            controller,
            widget,
            0,
            false,
            false
        )
    end
end

local function map_to_world(map_x, map_y)
    local world_x = (map_y * 460.0) - 123000.0
    local world_y = (map_x * 460.0) + 158000.0
    return world_x, world_y
end

local function add_map_marker(map_x, map_y)
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
    location_manager:AddLocalCustomMarker(
        {X = world_x, Y = world_y, Z = 0.0},
        MARKER_ICON_TYPE
    )
    log(string.format("Placed map marker at %.1f, %.1f", map_x, map_y))
end

local function process_marker_command(command)
    local payload = command:match("^[^;]+;(.+)$")
    if not payload then
        log("Ignored malformed marker command")
        return
    end

    local coordinates = {}
    for pair in payload:gmatch("[^;]+") do
        local x, y = pair:match("^(-?[%d%.]+),(-?[%d%.]+)$")
        if x and y then
            table.insert(coordinates, {x = tonumber(x), y = tonumber(y)})
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
        for _, coordinate in ipairs(coordinates) do
            local ok, message = pcall(
                add_map_marker,
                coordinate.x,
                coordinate.y
            )
            if not ok then
                log("Map marker failed: " .. tostring(message))
            end
        end
    end)
end

local function build_overlay()
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
    browser_widget.InitialURL = COMPANION_URL
    browser_widget.bSupportsTransparency = true

    local slot = canvas:AddChildToCanvas(browser_widget)
    slot:SetAnchors({
        Minimum = {X = 0.10, Y = 0.08},
        Maximum = {X = 0.90, Y = 0.92}
    })
    slot:SetOffsets({Left = 0, Top = 0, Right = 0, Bottom = 0})
    slot:SetAlignment({X = 0.5, Y = 0.5})

    root_widget:AddToViewport(9000)
    browser_widget:LoadURL(COMPANION_URL)
    root_widget:SetVisibility(1)
    visible = false
    log("Overlay created")
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
            browser_widget:LoadURL(COMPANION_URL)
            set_ui_input(controller, root_widget)
            log("Overlay opened")
        else
            set_game_input(controller)
            log("Overlay closed")
        end
    end)
end

RegisterKeyBind(Key.F2, toggle_overlay)

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
    return false
end)

log("Loaded. Press F2 in a world to open Pal Companion.")
