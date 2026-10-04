# Streaming structural validation of od -An -v -tu1 output; constant memory.
# No CRC or zlib decoder here. Optional pngcheck provides stronger validation.
BEGIN {
    split("137 80 78 71 13 10 26 10", sig, " ")
    pos = 0; chunkpos = 0; chunks = 0; done = 0; bad = 0
}
function reject() { bad = 1; exit 1 }
{
    for (i = 1; i <= NF; i++) {
        byte = $i + 0; pos++
        if (pos <= 8) { if (byte != sig[pos]) reject(); continue }
        if (done) reject()
        chunkpos++
        if (chunkpos <= 4) { len = len * 256 + byte; if (len > maxbytes) reject() }
        else if (chunkpos <= 8) {
            kind = kind sprintf("%c", byte)
            if (chunkpos == 8) {
                chunks++
                if (chunks == 1 && (kind != "IHDR" || len != 13)) reject()
                if (kind == "IHDR" && chunks != 1) reject()
                if (kind == "IDAT" && len > 0) idat = 1
                if (kind == "IEND" && (len != 0 || !idat)) reject()
            }
        } else if (kind == "IHDR") {
            if (chunkpos <= 12) w = w * 256 + byte
            else if (chunkpos <= 16) h = h * 256 + byte
            else if (chunkpos == 17 && byte != 8) reject()
            else if (chunkpos == 18 && byte != 0) reject()
            else if (chunkpos >= 19 && chunkpos <= 21 && byte != 0) reject()
        }
        if (chunkpos == len + 12) {
            if (kind == "IEND") done = 1
            chunkpos = 0; len = 0; kind = ""
        }
    }
}
END {
    if (bad || !done || pos != filesize || w != width || h != height) exit 1
}
