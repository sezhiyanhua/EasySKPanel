"""EasySKPanel
Author: SZ
bilibili: https://space.bilibili.com/12379590

Create bone sliders that control an object's shape keys in Blender.
Run the script in Object Mode, select the shape keys to control, and rerun it
to update or remove the generated panel.

Existing drivers not created by EmjPanel are preserved.
"""

import bpy
from bpy.props import BoolProperty, CollectionProperty, StringProperty
from bpy.types import Operator, PropertyGroup

PANEL_SUFFIX = "_EmjPanel"
MASTER_BONE_NAME = "EmjPanelRoot"
WIDGET_COLLECTION_NAME = "ShapeKey_Slider_Widgets"
ROW_SPACING = 0.16
BONE_LENGTH = 0.1
SLIDER_TRAVEL = 0.1
SLIDER_THICKNESS = 0.025
FRAME_MARGIN_LEFT = 0.06
FRAME_MARGIN_RIGHT_BASE = 0.08
FRAME_LABEL_CHAR_WIDTH = 0.012
FRAME_MARGIN_Z = 0.06


def _shape_keys_from_object(obj):
    if obj is None or not getattr(obj, "data", None):
        return []

    key_data = getattr(obj.data, "shape_keys", None)
    if key_data is None or not key_data.key_blocks:
        return []

    reference = key_data.reference_key
    return [key for key in key_data.key_blocks if key != reference]


def _find_panel_armature(target):
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        if obj.get("shape_key_slider_target") == target.name:
            return obj
    return None


def _target_from_panel(panel):
    target_name = panel.get("shape_key_slider_target")
    return bpy.data.objects.get(target_name) if target_name else None


def _create_panel_armature(target):
    panel_name = target.name + PANEL_SUFFIX
    armature_data = bpy.data.armatures.new(panel_name)
    panel = bpy.data.objects.new(panel_name, armature_data)
    bpy.context.collection.objects.link(panel)

    panel.matrix_world = target.matrix_world.copy()
    panel["shape_key_slider_target"] = target.name
    panel.show_in_front = True
    armature_data.display_type = "BBONE"
    armature_data.show_names = True
    return panel


def _rename_panel(panel, target):
    panel_name = target.name + PANEL_SUFFIX
    panel.name = panel_name
    panel.data.name = panel_name
    panel["shape_key_slider_target"] = target.name


def _activate_object(obj):
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _existing_shape_key_bones(panel):
    result = {}
    for pose_bone in panel.pose.bones:
        shape_name = pose_bone.get("shape_key_name")
        if shape_name:
            result[shape_name] = pose_bone
    return result


def _widget_collection():
    collection = bpy.data.collections.get(WIDGET_COLLECTION_NAME)
    if collection is None:
        collection = bpy.data.collections.new(WIDGET_COLLECTION_NAME)
        bpy.context.scene.collection.children.link(collection)
    collection.hide_render = True
    return collection


def _frame_widget(panel, width, height):
    widget_name = panel.name + "_Frame_Widget"
    widget = bpy.data.objects.get(widget_name)

    half_width = width * 0.5
    half_height = height * 0.5
    vertices = [
        (-half_width, -half_height, 0.0),
        (half_width, -half_height, 0.0),
        (half_width, half_height, 0.0),
        (-half_width, half_height, 0.0),
    ]
    edges = [(0, 1), (1, 2), (2, 3), (3, 0)]

    if widget is None or widget.type != "MESH":
        mesh = bpy.data.meshes.new(widget_name + "_Mesh")
        widget = bpy.data.objects.new(widget_name, mesh)
        _widget_collection().objects.link(widget)
    else:
        mesh = widget.data

    mesh.clear_geometry()
    mesh.from_pydata(vertices, edges, [])
    mesh.update()
    widget.display_type = "WIRE"
    widget.hide_render = True
    widget.hide_set(True)
    widget["shape_key_slider_widget"] = True
    widget["emj_panel_owner"] = panel.name
    return widget


def _panel_start_x(target):
    try:
        max_x = max(corner[0] for corner in target.bound_box)
        min_x = min(corner[0] for corner in target.bound_box)
        width = max(max_x - min_x, 1.0)
        return max_x + width * 0.15
    except (AttributeError, TypeError, ValueError):
        return 1.0


def _build_bones_and_frame(panel, target, shape_keys):
    _activate_object(panel)
    existing = _existing_shape_key_bones(panel)
    bpy.ops.object.mode_set(mode="EDIT")
    start_x = _panel_start_x(target)
    created_names = {}
    renamed_bones = {}

    old_master_pose = next(
        (
            bone
            for bone in panel.pose.bones
            if bone.get("shape_key_panel_master")
        ),
        None,
    )
    master = panel.data.edit_bones.get(MASTER_BONE_NAME)
    if master is None and old_master_pose is not None:
        master = panel.data.edit_bones.get(old_master_pose.name)
    if master is None:
        master = panel.data.edit_bones.new(MASTER_BONE_NAME)
    master.name = MASTER_BONE_NAME
    master.use_deform = False
    master.parent = None
    master_name = master.name

    for row, key in enumerate(shape_keys):
        pose_bone = existing.get(key.name)
        edit_bone = panel.data.edit_bones.get(pose_bone.name) if pose_bone else None
        if edit_bone is None:
            edit_bone = panel.data.edit_bones.new(key.name)

        z = -row * ROW_SPACING
        edit_bone.head = (start_x, 0.0, z)
        edit_bone.tail = (start_x, 0.0, z + BONE_LENGTH)

        old_name = edit_bone.name
        edit_bone.name = key.name
        if old_name != edit_bone.name:
            renamed_bones[old_name] = edit_bone.name
        edit_bone.use_deform = False
        edit_bone.bbone_x = SLIDER_THICKNESS
        edit_bone.bbone_z = SLIDER_THICKNESS
        edit_bone.parent = master
        edit_bone.use_connect = False
        created_names[key.name] = edit_bone.name

    slider_edit_bones = [panel.data.edit_bones[name] for name in created_names.values()]
    min_x = min(min(bone.head.x, bone.tail.x) for bone in slider_edit_bones)
    max_x = max(max(bone.head.x, bone.tail.x) for bone in slider_edit_bones)
    min_z = min(min(bone.head.z, bone.tail.z) for bone in slider_edit_bones)
    max_z = max(max(bone.head.z, bone.tail.z) for bone in slider_edit_bones)

    half_thickness = SLIDER_THICKNESS * 0.5
    longest_label_length = max(
        len(MASTER_BONE_NAME),
        *(len(shape_name) for shape_name in created_names),
    )
    label_space = FRAME_MARGIN_RIGHT_BASE + (
        min(longest_label_length, 32) * FRAME_LABEL_CHAR_WIDTH
    )
    frame_min_x = min_x - half_thickness - FRAME_MARGIN_LEFT
    frame_max_x = max_x + SLIDER_TRAVEL + half_thickness + label_space
    frame_min_z = min_z - half_thickness - FRAME_MARGIN_Z
    frame_max_z = max_z + half_thickness + FRAME_MARGIN_Z
    frame_width = frame_max_x - frame_min_x
    frame_height = frame_max_z - frame_min_z
    frame_center_x = (frame_min_x + frame_max_x) * 0.5
    frame_center_z = (frame_min_z + frame_max_z) * 0.5

    master.head = (frame_center_x, 0.0, frame_center_z)
    master.tail = (frame_center_x, 0.0, frame_center_z + BONE_LENGTH)

    for edit_bone in panel.data.edit_bones:
        edit_bone.use_deform = False

    bpy.ops.object.mode_set(mode="POSE")

    for shape_name, bone_name in created_names.items():
        pose_bone = panel.pose.bones[bone_name]
        pose_bone["shape_key_name"] = shape_name

        constraint = pose_bone.constraints.get("Shape Key Slider 0..1")
        if constraint is None:
            constraint = pose_bone.constraints.new(type="LIMIT_LOCATION")
            constraint.name = "Shape Key Slider 0..1"
        constraint.owner_space = "LOCAL"
        constraint.use_transform_limit = True
        constraint.use_min_x = True
        constraint.use_max_x = True
        constraint.min_x = 0.0
        constraint.max_x = SLIDER_TRAVEL

        constraint.use_min_y = True
        constraint.use_max_y = True
        constraint.min_y = 0.0
        constraint.max_y = 0.0

        constraint.use_min_z = True
        constraint.use_max_z = True
        constraint.min_z = 0.0
        constraint.max_z = 0.0
        existing[shape_name] = pose_bone

    master_pose = panel.pose.bones[master_name]
    master_pose["shape_key_panel_master"] = True
    master_pose.custom_shape = _frame_widget(panel, frame_width, frame_height)
    if hasattr(master_pose, "use_custom_shape_bone_size"):
        master_pose.use_custom_shape_bone_size = False
    if hasattr(master_pose, "custom_shape_scale_xyz"):
        master_pose.custom_shape_scale_xyz = (1.0, 1.0, 1.0)
    if hasattr(master_pose, "custom_shape_translation"):
        master_pose.custom_shape_translation = (0.0, 0.0, 0.0)
    if hasattr(master_pose, "custom_shape_rotation_euler"):
        master_pose.custom_shape_rotation_euler = (0.0, 0.0, 0.0)
    master_pose.lock_location = (False, False, False)
    master_pose.lock_rotation = (False, False, False)
    master_pose.lock_rotation_w = False
    master_pose.lock_scale = (False, False, False)

    return existing, master_pose, renamed_bones


def _retarget_renamed_slider_drivers(key_data, panel, renamed_bones):
    if not renamed_bones or key_data.animation_data is None:
        return
    for fcurve in key_data.animation_data.drivers:
        for variable in fcurve.driver.variables:
            if variable.type != "TRANSFORMS":
                continue
            for variable_target in variable.targets:
                if variable_target.id != panel:
                    continue
                new_name = renamed_bones.get(variable_target.bone_target)
                if new_name:
                    variable_target.bone_target = new_name


def _value_driver(key_data, shape_key):
    animation_data = key_data.animation_data
    if animation_data is None:
        return None
    data_path = shape_key.path_from_id("value")
    return next(
        (fcurve for fcurve in animation_data.drivers if fcurve.data_path == data_path),
        None,
    )


def _update_owned_driver_scale(fcurve, panel, pose_bone):
    for variable in fcurve.driver.variables:
        if variable.type != "TRANSFORMS":
            continue
        if any(
            target.id == panel and target.bone_target == pose_bone.name
            for target in variable.targets
        ):
            fcurve.driver.expression = (
                f"min(max({variable.name} / {SLIDER_TRAVEL:.6g}, 0.0), 1.0)"
            )
            return True
    return False


def _add_driver(shape_key, panel, pose_bone):
    fcurve = shape_key.driver_add("value")
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    driver.expression = (
        f"min(max(emj_slider / {SLIDER_TRAVEL:.6g}, 0.0), 1.0)"
    )

    variable = driver.variables.new()
    variable.name = "emj_slider"
    variable.type = "TRANSFORMS"
    target = variable.targets[0]
    target.id = panel
    target.bone_target = pose_bone.name
    target.transform_type = "LOC_X"
    target.transform_space = "LOCAL_SPACE"


def _driver_is_owned_by_panel(fcurve, panel, slider_names):
    for variable in fcurve.driver.variables:
        if variable.type != "TRANSFORMS" or variable.name not in {
            "emj_slider",
            "slider",  # Legacy compatibility.
        }:
            continue
        for variable_target in variable.targets:
            if (
                variable_target.id == panel
                and variable_target.bone_target in slider_names
                and variable_target.transform_type == "LOC_X"
                and variable_target.transform_space == "LOCAL_SPACE"
            ):
                return True
    return False


def _remove_panel_and_owned_drivers(panel, target):
    slider_names = {
        pose_bone.name
        for pose_bone in panel.pose.bones
        if pose_bone.get("shape_key_name")
    }
    removed_drivers = 0

    key_data = None
    if target is not None and getattr(target, "data", None) is not None:
        key_data = getattr(target.data, "shape_keys", None)
    if key_data is not None and key_data.animation_data is not None:
        for fcurve in list(key_data.animation_data.drivers):
            if _driver_is_owned_by_panel(fcurve, panel, slider_names):
                key_data.animation_data.drivers.remove(fcurve)
                removed_drivers += 1

    widgets = []
    for pose_bone in panel.pose.bones:
        widget = pose_bone.custom_shape
        if (
            widget is not None
            and widget.get("shape_key_slider_widget")
            and widget.get("emj_panel_owner") in {None, panel.name}
        ):
            widgets.append(widget)

    _activate_object(panel)
    if panel.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    armature_data = panel.data
    bpy.data.objects.remove(panel, do_unlink=True)
    if armature_data.users == 0:
        bpy.data.armatures.remove(armature_data)

    for widget in widgets:
        widget_data = widget.data
        bpy.data.objects.remove(widget, do_unlink=True)
        if widget_data is not None and widget_data.users == 0:
            bpy.data.meshes.remove(widget_data)

    if target is not None and target.name in bpy.context.view_layer.objects:
        _activate_object(target)

    message = f"EmjPanel removed: deleted {removed_drivers} owned driver(s)."
    print(message)
    try:
        bpy.context.workspace.status_text_set(text=message)
    except (AttributeError, RuntimeError):
        pass
    return removed_drivers


def _create_panel_for_shape_keys(target, selected_names):
    shape_keys = _shape_keys_from_object(target)
    if not shape_keys:
        raise RuntimeError(f'Object "{target.name}" has no controllable shape keys.')

    key_data = target.data.shape_keys
    # Preserve drivers not created by EmjPanel.
    available_shape_keys = [
        shape_key
        for shape_key in shape_keys
        if shape_key.name in selected_names
        and _value_driver(key_data, shape_key) is None
    ]
    if not available_shape_keys:
        raise RuntimeError("No eligible shape keys were selected.")

    panel = _create_panel_armature(target)
    _rename_panel(panel, target)
    bone_by_shape, master_bone, renamed_bones = _build_bones_and_frame(
        panel, target, available_shape_keys
    )
    _retarget_renamed_slider_drivers(key_data, panel, renamed_bones)

    added = 0
    for shape_key in available_shape_keys:
        _add_driver(shape_key, panel, bone_by_shape[shape_key.name])
        added += 1

    _activate_object(panel)
    bpy.ops.object.mode_set(mode="POSE")

    message = (
        f"Shape-key panel ready: added {added} selected driver(s)."
    )
    print(message)
    try:
        bpy.context.workspace.status_text_set(text=message)
    except (AttributeError, RuntimeError):
        pass
    return panel


class EMJ_PG_shape_key_choice(PropertyGroup):
    name: StringProperty()
    def _keep_external_driver_unselected(self, context):
        if self.has_driver and self.selected:
            self.selected = False

    selected: BoolProperty(name="", update=_keep_external_driver_unselected)
    has_driver: BoolProperty(default=False)


class EMJ_OT_set_all_choices(Operator):
    bl_idname = "object.emj_set_all_shape_key_choices"
    bl_label = "Set All EmjPanel Shape Key Choices"
    bl_options = {"INTERNAL"}

    selected: BoolProperty(default=True)

    def execute(self, context):
        for item in context.window_manager.emj_shape_key_choices:
            if not item.has_driver:
                item.selected = self.selected
        return {"FINISHED"}


class EMJ_OT_choose_shape_keys(Operator):
    bl_idname = "object.emj_choose_shape_keys"
    bl_label = "Choose Shape Keys for EmjPanel"
    bl_options = {"REGISTER", "UNDO"}

    target_name: StringProperty(options={"HIDDEN"})

    def invoke(self, context, event):
        active = context.active_object
        if active is None:
            self.report({"ERROR"}, "Select a mesh with shape keys first.")
            return {"CANCELLED"}

        if active.type == "ARMATURE" and active.get("shape_key_slider_target"):
            panel = active
            target = _target_from_panel(panel)
        else:
            target = active
            panel = _find_panel_armature(target)

        if target is None:
            self.report({"ERROR"}, "The EmjPanel source object no longer exists.")
            return {"CANCELLED"}

        shape_keys = _shape_keys_from_object(target)
        if not shape_keys:
            self.report({"ERROR"}, "The active object has no shape keys.")
            return {"CANCELLED"}

        self.target_name = target.name
        choices = context.window_manager.emj_shape_key_choices
        choices.clear()
        active_key = target.active_shape_key
        eligible_count = 0
        slider_names = {
            pose_bone.name
            for pose_bone in panel.pose.bones
            if pose_bone.get("shape_key_name")
        } if panel is not None else set()

        for shape_key in shape_keys:
            item = choices.add()
            item.name = shape_key.name
            existing_driver = _value_driver(target.data.shape_keys, shape_key)
            owned_driver = (
                existing_driver is not None
                and panel is not None
                and _driver_is_owned_by_panel(existing_driver, panel, slider_names)
            )
            item.has_driver = existing_driver is not None and not owned_driver
            item.selected = owned_driver or (
                panel is None and shape_key == active_key and not item.has_driver
            )
            if not item.has_driver:
                eligible_count += 1

        if eligible_count == 0:
            self.report({"INFO"}, "All shape keys already have drivers.")
            return {"CANCELLED"}
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Select the shape keys to control:")
        button_row = layout.row(align=True)
        select_all = button_row.operator(
            "object.emj_set_all_shape_key_choices",
            text="Select All",
            icon="CHECKBOX_HLT",
        )
        select_all.selected = True

        select_none = button_row.operator(
            "object.emj_set_all_shape_key_choices",
            text="Select None",
            icon="CHECKBOX_DEHLT",
        )
        select_none.selected = False
        column = layout.column(align=True)
        for item in context.window_manager.emj_shape_key_choices:
            row = column.row(align=True)
            row.enabled = not item.has_driver
            row.prop(item, "selected", text=item.name, toggle=True)
            if item.has_driver:
                row.label(text="Existing driver", icon="DRIVER")

    def execute(self, context):
        target = bpy.data.objects.get(self.target_name)
        if target is None:
            self.report({"ERROR"}, "The source object no longer exists.")
            return {"CANCELLED"}

        selected_names = {
            item.name
            for item in context.window_manager.emj_shape_key_choices
            if item.selected and not item.has_driver
        }
        try:
            existing_panel = _find_panel_armature(target)
            if existing_panel is not None:
                _remove_panel_and_owned_drivers(existing_panel, target)
            if selected_names:
                _create_panel_for_shape_keys(target, selected_names)
        except RuntimeError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        if not selected_names:
            self.report({"INFO"}, "EmjPanel controls removed.")
        return {"FINISHED"}


CLASSES = (
    EMJ_PG_shape_key_choice,
    EMJ_OT_set_all_choices,
    EMJ_OT_choose_shape_keys,
)


def register():
    if hasattr(bpy.types.WindowManager, "emj_shape_key_choices"):
        del bpy.types.WindowManager.emj_shape_key_choices
    for class_name in reversed(tuple(cls.__name__ for cls in CLASSES)):
        old_class = getattr(bpy.types, class_name, None)
        if old_class is None:
            continue
        try:
            bpy.utils.unregister_class(old_class)
        except RuntimeError:
            pass
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.emj_shape_key_choices = CollectionProperty(
        type=EMJ_PG_shape_key_choice
    )


def build_shape_key_slider_panel():
    active = bpy.context.active_object
    if active is None:
        raise RuntimeError("Select an object with shape keys or its EmjPanel first.")

    bpy.ops.object.emj_choose_shape_keys("INVOKE_DEFAULT")
    return None


if __name__ == "__main__":
    register()
    build_shape_key_slider_panel()
