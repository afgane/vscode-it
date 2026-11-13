#!/bin/bash
# Verify the 1.105.1-3 image the way Galaxy's Docker runner uses it.
IMG=${1:-ksuderman/galaxy-vscode:1.105.1-3}
S=$(mktemp -d)
P="--platform linux/amd64"
echo "== image config"
docker inspect "$IMG" --format 'Entrypoint={{json .Config.Entrypoint}} Cmd={{json .Config.Cmd}} User={{.Config.User}}'
echo "== 1. a command passed to docker run must execute (not be swallowed)"
docker run --rm $P "$IMG" /bin/sh -c 'echo COMMAND-RAN; command -v python3 R gcloud micromamba | tr "\n" " "; echo'
echo "== 2. bare docker run falls back to CMD (start.sh), which must refuse without EP_PATH"
docker run --rm $P "$IMG" 2>&1 | head -3; echo "exit=${PIPESTATUS[0]}"
echo "== 3. simulate Galaxy's docker run: tool_script.sh as the command, uid 10001, job dir mounted"
JOB=$(mktemp -d $S/jobdir.XXXX); chmod 777 "$JOB"
mkdir -p "$JOB/inputs"; printf 'chr1\t1\t2\n' > "$JOB/inputs/dataset_1.dat"
cat > "$JOB/tool_script.sh" << 'TS'
export EP_PATH=/galaxy/its/ep/1/tok/
export GALAXY_URL=http://example.invalid/galaxy API_KEY=fake HISTORY_ID=abc
mkdir -p workspace/inputs && ln -sf /jobdir/inputs/dataset_1.dat 'workspace/inputs/regions.bed' && exec /opt/galaxy-vscode/start.sh
TS
CID=$(docker run -d $P --user 10001:10001 -w /jobdir -v "$JOB:/jobdir" -p 3300:3000 "$IMG" /bin/sh /jobdir/tool_script.sh)
for i in $(seq 1 30); do code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:3300/galaxy/its/ep/1/tok/); [ "$code" = 200 ] && break; sleep 2; done
echo "GET /galaxy/its/ep/1/tok/ -> $code after ${i}x2s"
echo "wrong path -> $(curl -s -o /dev/null -w '%{http_code}' http://localhost:3300/)"
echo "input link: $(ls -l $JOB/workspace/inputs 2>/dev/null | tail -1)"
echo "README: $(ls $JOB/workspace/README.md 2>/dev/null) settings: $(ls $JOB/home/data/User/settings.json 2>/dev/null)"
docker logs "$CID" 2>&1 | grep -i "error\|denied" | head -3
docker rm -f "$CID" > /dev/null
chmod -R u+w "$JOB"; rm -rf "$JOB"
echo "== done"
