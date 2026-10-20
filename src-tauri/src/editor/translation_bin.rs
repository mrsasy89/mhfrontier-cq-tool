//! Translation-only binary handling. No gameplay structures are reserialized.
use encoding_rs::SHIFT_JIS;
use serde::{Deserialize, Serialize};

pub const MAX_FILE: usize = 32 * 1024 * 1024;
const ECD: u32 = 0x1a646365;
const JPK: u32 = 0x1a524b4a;
type Result<T> = std::result::Result<T, String>;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct TranslationStrings {
    pub title: String,
    pub main_objective: String,
    pub sub_a_objective: String,
    pub sub_b_objective: String,
    pub clear_reqs: String,
    pub fail_reqs: String,
    pub contractor: String,
    pub description: String,
}

impl TranslationStrings {
    fn fields(&self) -> [&str; 8] {
        [
            &self.title, &self.main_objective, &self.sub_a_objective,
            &self.sub_b_objective, &self.clear_reqs, &self.fail_reqs,
            &self.contractor, &self.description,
        ]
    }
}

#[derive(Clone)]
pub enum Layer {
    Ecd(Vec<u8>),
    Jpk(Vec<u8>, u16),
}

pub fn u16_at(data: &[u8], pos: usize) -> Result<u16> {
    let bytes = data.get(pos..pos + 2).ok_or("Truncated uint16")?;
    Ok(u16::from_le_bytes([bytes[0], bytes[1]]))
}

pub fn u32_at(data: &[u8], pos: usize) -> Result<u32> {
    let bytes = data.get(pos..pos + 4).ok_or("Truncated uint32")?;
    Ok(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
}

fn put_u32(data: &mut [u8], pos: usize, value: u32) {
    data[pos..pos + 4].copy_from_slice(&value.to_le_bytes());
}

pub fn stamp(data: &[u8]) -> String {
    format!("{}:{:08x}", data.len(), crc32fast::hash(data))
}

pub fn read_strings(data: &[u8]) -> Result<(u16, TranslationStrings)> {
    let body = u32_at(data, 0)? as usize;
    if body < 0x40 || body.checked_add(0x30).filter(|end| *end <= data.len()).is_none() {
        return Err("Invalid raw quest header pointer".into());
    }
    let id = u16_at(data, body + 0x2e)?;
    let table = u32_at(data, body + 0x28)? as usize;
    if table < body + 0x30 || table.checked_add(32).filter(|end| *end <= data.len()).is_none() {
        return Err("Quest string table is outside the file".into());
    }
    let mut strings = Vec::new();
    for index in 0..8 {
        let pointer = u32_at(data, table + index * 4)? as usize;
        if pointer < table + 32 || pointer >= data.len() {
            return Err(format!("String {} pointer is outside its text region", index + 1));
        }
        let tail = &data[pointer..std::cmp::min(data.len(), pointer + 8193)];
        let length = tail.iter().position(|byte| *byte == 0)
            .ok_or_else(|| format!("String {} has no bounded NUL terminator", index + 1))?;
        let text = SHIFT_JIS.decode_without_bom_handling_and_without_replacement(&tail[..length])
            .ok_or_else(|| format!("String {} is not valid Shift-JIS", index + 1))?;
        if text.chars().any(|c| c.is_control() && c != '\n' && c != '\r' && c != '\t') {
            return Err(format!("String {} contains unsupported control codes", index + 1));
        }
        strings.push(text.into_owned());
    }
    Ok((id, TranslationStrings {
        title: strings[0].clone(), main_objective: strings[1].clone(),
        sub_a_objective: strings[2].clone(), sub_b_objective: strings[3].clone(),
        clear_reqs: strings[4].clone(), fail_reqs: strings[5].clone(),
        contractor: strings[6].clone(), description: strings[7].clone(),
    }))
}

pub fn patch_strings(data: &[u8], strings: &TranslationStrings) -> Result<Vec<u8>> {
    read_strings(data)?;
    let body = u32_at(data, 0)? as usize;
    let mut text = Vec::new();
    for field in strings.fields() {
        if field.chars().any(|c| c.is_control() && c != '\n' && c != '\r' && c != '\t') {
            return Err("Translation contains NUL or unsupported control characters".into());
        }
        let (encoded, _, errors) = SHIFT_JIS.encode(field);
        if errors || encoded.len() > 8192 {
            return Err("Translation is not losslessly encodable or exceeds 8192 bytes".into());
        }
        text.push(encoded.into_owned());
    }
    // Erupe v9.6.1 ZZ enumeration: 384 fixed bytes + eight encoded texts <= 896.
    if text.iter().map(|field| field.len()).sum::<usize>() > 512 {
        return Err("The eight texts exceed the Erupe v9.6.1 ZZ event budget of 512 Shift-JIS bytes. Shorten them before exporting.".into());
    }
    if read_strings(data)?.1 == *strings { return Ok(data.to_vec()); }
    let mut output = data.to_vec();
    while output.len() % 4 != 0 { output.push(0); }
    let table = output.len();
    output.resize(table + 32, 0);
    for (index, field) in text.iter().enumerate() {
        let pointer = output.len() as u32;
        put_u32(&mut output, table + index * 4, pointer);
        output.extend_from_slice(field);
        output.push(0);
    }
    if output.len() > MAX_FILE { return Err("Translated quest exceeds the size limit".into()); }
    put_u32(&mut output, body + 0x28, table as u32);
    if read_strings(&output)?.1 != *strings { return Err("Translated text verification failed".into()); }
    Ok(output)
}

struct Symbols<'a> {
    data: &'a [u8], pos: usize, root: Option<u16>, table: usize,
    bits: u8, remaining: u8,
}

impl<'a> Symbols<'a> {
    fn new(data: &'a [u8], offset: usize, huffman: bool) -> Result<Self> {
        if !huffman {
            return Ok(Self { data, pos: offset, root: None, table: 0, bits: 0, remaining: 0 });
        }
        let root = u16_at(data, offset)?;
        if !(256..=511).contains(&root) { return Err("Unsupported Huffman root".into()); }
        let table = offset + 2;
        let pos = table + (root as usize - 255) * 4;
        if pos > data.len() { return Err("Truncated Huffman table".into()); }
        Ok(Self { data, pos, root: Some(root), table, bits: 0, remaining: 0 })
    }

    fn byte(&mut self) -> Result<u8> {
        let root = match self.root {
            None => {
                let value = *self.data.get(self.pos).ok_or("Truncated JPK stream")?;
                self.pos += 1;
                return Ok(value);
            }
            Some(root) => root,
        };
        let mut node = root;
        while node >= 256 {
            if self.remaining == 0 {
                self.bits = *self.data.get(self.pos).ok_or("Truncated Huffman stream")?;
                self.pos += 1;
                self.remaining = 8;
            }
            self.remaining -= 1;
            let bit = (self.bits >> self.remaining) & 1;
            let next = u16_at(self.data, self.table + (node as usize - 256) * 4 + bit as usize * 2)?;
            if next >= node { return Err("Invalid or cyclic Huffman table".into()); }
            node = next;
        }
        Ok(node as u8)
    }
}

fn decode_jpk(data: &[u8], kind: u16) -> Result<Vec<u8>> {
    let offset = u32_at(data, 8)? as usize;
    let size = u32_at(data, 12)? as usize;
    if size > MAX_FILE || offset < 16 || offset > data.len() {
        return Err("Invalid JPK size or stream offset".into());
    }
    if kind == 0 {
        return Ok(data.get(offset..offset + size).ok_or("Truncated raw JPK payload")?.to_vec());
    }
    if ![3, 4].contains(&kind) { return Err(format!("Unsupported JPK type {}; HFIRW/type 2 requires separate validation", kind)); }
    let mut symbols = Symbols::new(data, offset, kind != 3)?;
    let mut output = Vec::with_capacity(size);
    let mut flags = 0u8;
    let mut remaining = 0u8;
    fn bit(symbols: &mut Symbols<'_>, flags: &mut u8, remaining: &mut u8) -> Result<u8> {
        if *remaining == 0 { *flags = symbols.byte()?; *remaining = 8; }
        *remaining -= 1;
        Ok((*flags >> *remaining) & 1)
    }
    while output.len() < size {
        if bit(&mut symbols, &mut flags, &mut remaining)? == 0 {
            output.push(symbols.byte()?);
            continue;
        }
        let distance;
        let length;
        if bit(&mut symbols, &mut flags, &mut remaining)? == 0 {
            let high = bit(&mut symbols, &mut flags, &mut remaining)?;
            let low = bit(&mut symbols, &mut flags, &mut remaining)?;
            length = ((high << 1) | low) as usize + 3;
            distance = symbols.byte()? as usize + 1;
        } else {
            let high = symbols.byte()?;
            let low = symbols.byte()?;
            let code = high >> 5;
            let offset = (((high & 31) as usize) << 8) | low as usize;
            distance = offset + 1;
            if code != 0 { length = code as usize + 2; }
            else if bit(&mut symbols, &mut flags, &mut remaining)? == 0 {
                let mut code = 0usize;
                for _ in 0..4 { code = (code << 1) | bit(&mut symbols, &mut flags, &mut remaining)? as usize; }
                length = code + 10;
            } else {
                let code = symbols.byte()?;
                if code == 255 {
                    let count = offset + 27;
                    if count > size - output.len() { return Err("JPK literal run exceeds declared size".into()); }
                    for _ in 0..count { output.push(symbols.byte()?); }
                    continue;
                }
                length = code as usize + 26;
            }
        }
        if distance > output.len() || length > size - output.len() {
            return Err("JPK copy points outside decoded data".into());
        }
        for _ in 0..length {
            output.push(output[output.len() - distance]);
        }
    }
    Ok(output)
}

fn encode_jpk(data: &[u8], prefix: &[u8], kind: u16) -> Result<Vec<u8>> {
    let mut output = prefix.to_vec();
    output[6..8].copy_from_slice(&kind.to_le_bytes());
    put_u32(&mut output, 12, data.len() as u32);
    match kind {
        0 => output.extend_from_slice(data),
        3 => {
            // Literal-only LZ avoids changing the compression algorithm while
            // keeping the encoder small and auditable. Files can be larger.
            for chunk in data.chunks(8) { output.push(0); output.extend_from_slice(chunk); }
        }
        _ => return Err("This JPK type requires explicit conversion to JPK3".into()),
    }
    if output.len() > MAX_FILE { return Err("Repacked quest exceeds size limit".into()); }
    Ok(output)
}

const ECD_RANDOM: [u32; 12] = [
    0x4a4b522e, 1, 0x10dcd, 1, 0x10dcd, 1,
    0x10dcd, 1, 0x19660d, 3, 0x7d2b89dd, 1,
];

fn ecd_crypt(data: &[u8], header: &[u8], encrypt: bool) -> Result<Vec<u8>> {
    let index = u16_at(header, 4)? as usize;
    if index > 5 { return Err("Unsupported ECD key index".into()); }
    let crc = u32_at(header, 12)?;
    let mut random = crc.rotate_left(16) | 1;
    let mut next = || {
        random = random.wrapping_mul(ECD_RANDOM[index * 2]).wrapping_add(ECD_RANDOM[index * 2 + 1]);
        random
    };
    let mut previous = next() as u8;
    let mut output = Vec::with_capacity(data.len());
    for &byte in data {
        let mut pad = next();
        if encrypt {
            let (mut a, mut b) = (0u32, 0u32);
            for _ in 0..8 { let temp = pad ^ a; a = b; b = (b ^ temp) & 255; pad >>= 4; }
            let mut low = byte as u32;
            let mut high = (low >> 4) & 255;
            high ^= a; low ^= b; high ^= low;
            output.push(((low & 15) | ((high & 15) << 4)) as u8 ^ previous);
            previous = byte;
        } else {
            let mut a = (byte ^ previous) as u32;
            let mut b = a >> 4;
            for _ in 0..8 { let temp = pad ^ a; a = b; b = (b ^ temp) & 255; pad >>= 4; }
            previous = ((b & 15) | ((a & 15) << 4)) as u8;
            output.push(previous);
        }
    }
    Ok(output)
}

pub fn unwrap(data: &[u8]) -> Result<(Vec<u8>, Vec<Layer>)> {
    let mut data = data.to_vec();
    let mut layers = Vec::new();
    for _ in 0..5 {
        if data.len() > MAX_FILE { return Err("Decoded file exceeds size limit".into()); }
        match u32_at(&data, 0)? {
            ECD => {
                let size = u32_at(&data, 8)? as usize;
                if size > MAX_FILE || data.len() != size + 16 { return Err("Invalid ECD payload size".into()); }
                let header = data[..16].to_vec();
                data = ecd_crypt(&data[16..], &header, false)?;
                if crc32fast::hash(&data) != u32_at(&header, 12)? { return Err("ECD checksum mismatch".into()); }
                layers.push(Layer::Ecd(header));
            }
            JPK => {
                let kind = u16_at(&data, 6)?;
                let offset = u32_at(&data, 8)? as usize;
                if offset < 16 || offset > 4096 || offset > data.len() { return Err("Invalid JPK header region".into()); }
                let prefix = data[..offset].to_vec();
                data = decode_jpk(&data, kind)?;
                layers.push(Layer::Jpk(prefix, kind));
            }
            _ => return Ok((data, layers)),
        }
    }
    Err("Too many nested compression/encryption layers".into())
}

pub fn wrap(raw: &[u8], layers: &[Layer], repack_jpk3: bool) -> Result<(Vec<u8>, bool)> {
    let mut output = raw.to_vec();
    let mut converted = false;
    for layer in layers.iter().rev() {
        output = match layer {
            Layer::Jpk(prefix, kind) => {
                let kind = if *kind == 2 || *kind == 4 {
                    if !repack_jpk3 { return Err("Enable explicit JPK3 conversion to export Huffman-compressed quests".into()); }
                    converted = true; 3
                } else { *kind };
                encode_jpk(&output, prefix, kind)?
            }
            Layer::Ecd(header) => {
                let mut header = header.clone();
                put_u32(&mut header, 8, output.len() as u32);
                put_u32(&mut header, 12, crc32fast::hash(&output));
                let encrypted = ecd_crypt(&output, &header, true)?;
                header.extend_from_slice(&encrypted);
                header
            }
        };
        if output.len() > MAX_FILE { return Err("Encoded file exceeds size limit".into()); }
    }
    if unwrap(&output)?.0 != raw { return Err("Encoded quest round-trip verification failed".into()); }
    Ok((output, converted))
}

pub fn layer_names(layers: &[Layer]) -> Vec<String> {
    layers.iter().map(|layer| match layer {
        Layer::Ecd(_) => "ECD".into(), Layer::Jpk(_, kind) => format!("JPK{}", kind),
    }).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Vec<u8> {
        let mut data = vec![0u8; 0x160];
        put_u32(&mut data, 0, 0xc0);
        put_u32(&mut data, 0xe8, 0x120);
        data[0xee..0xf0].copy_from_slice(&64551u16.to_le_bytes());
        for index in 0..8 {
            let pointer = data.len();
            put_u32(&mut data, 0x120 + index * 4, pointer as u32);
            data.extend_from_slice(b"Original\0");
        }
        data
    }

    #[test]
    fn append_changes_only_pointer_in_original_region() {
        let data = sample();
        let mut strings = read_strings(&data).unwrap().1;
        strings.description = "Translated\ntext".into();
        let output = patch_strings(&data, &strings).unwrap();
        assert_eq!(&data[..0xe8], &output[..0xe8]);
        assert_eq!(&data[0xec..], &output[0xec..data.len()]);
        assert_eq!(read_strings(&output).unwrap().1, strings);
    }

    #[test]
    fn unsupported_characters_and_nul_are_rejected() {
        let data = sample();
        let mut strings = read_strings(&data).unwrap().1;
        strings.title = "Emoji 😀".into();
        assert!(patch_strings(&data, &strings).is_err());
        strings.title = "NUL\0".into();
        assert!(patch_strings(&data, &strings).is_err());
    }

    #[test]
    fn malformed_text_pointer_is_rejected() {
        let mut data = sample();
        put_u32(&mut data, 0x120, u32::MAX);
        assert!(read_strings(&data).is_err());
    }

    #[test]
    fn zz_event_budget_is_enforced_and_noop_preserves_bytes() {
        let data = sample();
        let mut strings = read_strings(&data).unwrap().1;
        assert_eq!(patch_strings(&data, &strings).unwrap(), data);
        strings.description = "x".repeat(513);
        assert!(patch_strings(&data, &strings).is_err());
    }

    #[test]
    fn jpk_literal_and_ecd_layers_round_trip() {
        let raw = sample();
        let mut header = vec![0; 16];
        put_u32(&mut header, 0, JPK);
        put_u32(&mut header, 8, 16);
        let mut ecd = vec![0; 16];
        put_u32(&mut ecd, 0, ECD);
        ecd[4] = 4;
        let layers = vec![Layer::Ecd(ecd), Layer::Jpk(header, 3)];
        let output = wrap(&raw, &layers, false).unwrap().0;
        assert_eq!(unwrap(&output).unwrap().0, raw);
    }

    #[test]
    fn huffman_conversion_is_explicit() {
        let mut prefix = vec![0; 16];
        put_u32(&mut prefix, 0, JPK);
        put_u32(&mut prefix, 8, 16);
        let layers = vec![Layer::Jpk(prefix, 4)];
        assert!(wrap(&sample(), &layers, false).is_err());
        assert!(wrap(&sample(), &layers, true).unwrap().1);
    }

    #[test]
    fn huffman_lz_literal_fixture() {
        let mut data = vec![0; 16];
        put_u32(&mut data, 0, JPK);
        data[6..8].copy_from_slice(&4u16.to_le_bytes());
        put_u32(&mut data, 8, 16);
        put_u32(&mut data, 12, 3);
        // Root 258 -> [257,C]; node 257 -> [B,256]; node 256 -> [0,A].
        // Huffman symbols [0,A,B,A] encode one LZ flag byte plus three literals.
        data.extend_from_slice(&258u16.to_le_bytes());
        for value in [0u16, 65, 66, 256, 257, 67] { data.extend_from_slice(&value.to_le_bytes()); }
        data.extend_from_slice(&[0b01001100, 0b01100000]);
        assert_eq!(unwrap(&data).unwrap().0, b"ABA");
    }
}
