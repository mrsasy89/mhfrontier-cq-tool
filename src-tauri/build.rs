fn main() {
    println!("cargo:rerun-if-env-changed=CQ_WINDOWS_SDK_BIN");
    let mut attributes = tauri_build::Attributes::default();
    if let Some(sdk_bin) = std::env::var_os("CQ_WINDOWS_SDK_BIN") {
        attributes =
            attributes.windows_attributes(tauri_build::WindowsAttributes::new().sdk_dir(sdk_bin));
    }
    tauri_build::try_build(attributes).expect("Failed to build Tauri resources");
}
