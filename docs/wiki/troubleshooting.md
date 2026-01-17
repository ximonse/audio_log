# Troubleshooting

## ffmpeg not found
Install FFmpeg and ensure `ffmpeg` and `ffprobe` are on PATH.

## ASR fails to load
`faster-whisper` requires model weights. Download once or set `ASR` to a smaller model.

## Timezone errors on Windows
Install `tzdata` (already in dependencies) so `Europe/Stockholm` resolves.

## Git & rättigheter (Windows)

### Problem: Git kan inte skriva till .git/config eller .git/index.lock
**Symptom**:
- `fatal: could not set 'remote.origin.url' to 'https://...'`
- `error: unable to create file .git/index.lock: Permission denied`

**Orsak**: En explicit eller ärvd DENY-regel i ACL blockerar skrivrättigheter på
`.git`. Ofta kommer den från ett okänt SID (S-1-5-21-...) via arv eller policy.

### Lösning (permanent): Bryt arv och ge explicit Full Control
**Detta är den fungerande lösningen** när DENY-regeln är skyddad och återkommer:

```bash
# 1. Inaktivera arv på .git (förhindrar att DENY-regeln återkommer)
icacls.exe .git //inheritance:r

# 2. Ge explicit Full Control till din användare
icacls.exe .git //grant "%USERNAME%:(OI)(CI)F" //T
```

**Varför detta fungerar**: Din explicita ALLOW-regel övertrumfar DENY-regeln, även om DENY:n fortfarande syns i ACL-listan.

### Lösning (temporär): Reset ACLs
Fungerar om DENY-regeln inte är skyddad:
```bash
icacls.exe .git //reset //T
```

Om du behöver ta bort en specifik DENY-regel:
```bash
# Hitta SID:et med: icacls .git
icacls.exe .git //remove:d "S-1-5-21-3812506538-2525201657-3089093768-748237673" //T
```

### Git Bash vs Windows-kommandon

När du kör Windows-kommandon i Git Bash:

**Fel sätt** (tolkas som sökvägar):
```bash
icacls .git /reset /T          # blir "C:/Program Files/Git/reset"
takeown /F .git /R /D Y        # "F:/" tolkas som enhet
```

**Rätt sätt** (tvingar flaggtolkning):
```bash
icacls.exe .git //reset //T
cmd /c "takeown /F .git /R /D Y"
```

### Vanliga ACL-kommandon

**Se nuvarande rättigheter**:
```bash
icacls .git
```

**Ta bort specifik DENY-regel**:
```bash
icacls.exe .git //remove:d "S-1-5-21-xxxxx" //T
```

**Ta ägarskap** (kräver admin):
```bash
cmd /c "takeown /F .git /R /D Y"
cmd /c "icacls .git /grant %USERNAME%:(OI)(CI)F /T"
```

### Git och filrättigheter

**Problem**: `git status` visar alla filer som ändrade (mode change)

**Lösning**: Ignorera filrättighetsändringar:
```bash
git config core.fileMode false
```

**Problem**: Line ending-varningar (CRLF/LF)

**Lösning**: Sätt line ending-hantering:
```bash
git config core.autocrlf true   # Windows (konverterar LF->CRLF vid checkout)
git config core.autocrlf input  # Linux/Mac (behåll LF)
```

### Git remote-problem

**Kolla nuvarande remotes**:
```bash
git remote -v
```

**Lägg till remote**:
```bash
git remote add origin https://github.com/user/repo.git
```

**Ändra remote URL**:
```bash
git remote set-url origin https://github.com/user/new-repo.git
```

**Ta bort remote**:
```bash
git remote remove origin
```

### Permission denied vid push

**Lösning 1**: Använd HTTPS med token istället för SSH
```bash
git remote set-url origin https://github.com/user/repo.git
```

**Lösning 2**: Konfigurera SSH-nycklar
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Lägg till publik nyckel (~/.ssh/id_ed25519.pub) på GitHub
```

### Git i WSL vs Windows

Om du har klonat repo i Windows och försöker använda det från WSL:
- ACL:er kan bråka mellan filsystem
- **Rekommendation**: Klona separat i WSL (`/home/user/projekt`)
- Eller använd `git config core.fileMode false` i båda miljöerna