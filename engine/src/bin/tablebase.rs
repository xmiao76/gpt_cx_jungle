use std::{fs, path::Path};
fn main() {
    let path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "engine/data/two_piece.bin".into());
    let bytes = jungle_engine::tablebase::generate();
    if std::env::args().any(|arg| arg == "--check") {
        assert_eq!(
            bytes,
            fs::read(&path).expect("Missing tablebase."),
            "Tablebase is not reproducible."
        );
    } else {
        if let Some(parent) = Path::new(&path).parent() {
            fs::create_dir_all(parent).unwrap();
        }
        fs::write(&path, &bytes).unwrap();
    }
    println!(
        "{}",
        serde_json::json!({"path":path,"bytes":bytes.len(),"checksum":format!("{:016x}",jungle_engine::tablebase::checksum(&bytes))})
    );
}
