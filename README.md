# EasySKPanel

EasySKPanel is a Blender Python script that creates bone sliders for controlling an object's shape keys.

The script lets you choose which shape keys to expose, creates or updates an armature-based slider panel, and preserves existing drivers that were not created by EasySKPanel.

## Requirements

- Blender with Python scripting support
- A mesh object containing one or more shape keys

## Usage

1. Download `EasySKPanel.py`.
2. Open Blender and switch to the **Scripting** workspace.
3. Open `EasySKPanel.py` in the Text Editor.
4. In Object Mode, select a mesh that contains shape keys.
5. Click **Run Script**.
6. Choose the shape keys you want to control and confirm.

Run the script again with the source mesh or its generated EmjPanel selected to update or remove the controls.

## Notes

- Existing drivers not created by EasySKPanel are preserved.
- Save a backup of important `.blend` files before using scripts that modify a scene.
- The generated panel uses the `EmjPanel` name internally for compatibility with the script.

## Author

SZ

- [Bilibili](https://space.bilibili.com/12379590)

## License

Released under the [MIT License](LICENSE).
