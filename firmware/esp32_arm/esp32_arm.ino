#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

// =====================================================================
// ESP32 機器手臂韌體 (示範臂即時連動 + Python 播放控制)
//
// 序列埠指令 (115200, 每行以 \n 結尾)：
//   P,j1,j2,j3,j4,j5,j6  播放模式：直接設定六軸角度 (格式錯誤會被拒絕)
//   s / stop             緊急停止：手臂停在原地，忽略所有 P 指令
//   r / run              解除停止並回到即時連動 (從手臂跟隨示範臂)
//   C,j7,j8              排夾角度 (J7 第一排、J8 第二排)
//   C,OPEN / C,CLOSE     排夾全開 / 全關 (開機預設全開)
//   ?                    查詢狀態，回傳 STATE,<模式>,j1,...,j6,j7,j8
//
// 回傳訊息：
//   READY                       開機完成
//   DATA,j1,...,j6              即時連動模式下每 20ms 回報角度 (錄製用)
//   STATE,<模式>,j1,...,j8       回應 ? (模式: RUNNING / PLAYBACK / EMERGENCY_STOP)
//   STATUS:CLAMP,j7,j8           排夾動作完成回報
//   STATUS:<模式>                模式切換時回報
//   ERR:<原因>                   指令被拒絕
// =====================================================================

// 建立 PCA9685 物件 (預設 I2C 位址 0x40)
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);

#define SERVOMIN  125
#define SERVOMAX  590

#define MIN_ANGLE 5     // 最小允許安全角度
#define MAX_ANGLE 175   // 最大允許安全角度
#define MAX_SPEED 8     // 即時連動模式：每 20ms 允許變化的最大角度 (J1~J5 專用)
#define PLAYBACK_MAX_STEP 10  // 播放模式：每個封包 J1~J5 最多變化角度 (防止錯誤封包讓手臂暴衝)
#define LOOP_INTERVAL_MS 20   // 即時連動更新週期 (50Hz)
#define RX_MAX_LEN 64

// 排夾 (手牌架第一排 J7、第二排 J8)，接在 PCA9685 通道 6、7
const int CLAMP_CH[2]    = {6, 7};
const int CLAMP_OPEN[2]  = {0, 90};   // J7: 0 開 / J8: 90 開
const int CLAMP_CLOSE[2] = {90, 0};   // J7: 90 關 / J8: 0 關
int clampAngles[2] = {0, 90};

// 腳位定義 (J3 與 J4 已對調)
const int potPins[6] = {36, 39, 35, 34, 32, 33};

// 零點校正偏移量
int offset[6] = {
  16,  // J1 (底座旋轉)
  20,  // J2 (大臂)
  0,   // J3 (小臂)
  -20, // J4 (腕俯仰)
  8,   // J5 (腕旋轉)
  25   // J6 (夾爪 - 偏移量)
};

// J6 (夾爪) 靈敏度放大設定區 (示範臂 10° -> 馬達 90°~180°)
const int J6_INPUT_MIN = 85;
const int J6_INPUT_MAX = 95;
const int J6_OUTPUT_MIN = 90;
const int J6_OUTPUT_MAX = 180;

// 狀態變數
float filteredValues[6] = {0};
int lastOutputAngles[6] = {90, 90, 90, 90, 90, 90};
const float alpha = 0.15;

bool isEmergencyStop = false;   // 緊急停止狀態
bool isPlaybackMode = false;    // 是否為 Python 播放/遠端控制模式
bool stopRejectReported = false;
unsigned long lastUpdate = 0;
String rxBuffer;

int angleToPulse(int angle) {
  return map(angle, 0, 180, SERVOMIN, SERVOMAX);
}

void writeServo(int i, int angle) {
  pwm.setPWM(i, 0, angleToPulse(angle));
  lastOutputAngles[i] = angle;
}

const char* modeName() {
  if (isEmergencyStop) return "EMERGENCY_STOP";
  return isPlaybackMode ? "PLAYBACK" : "RUNNING";
}

void sendState() {
  Serial.print("STATE,");
  Serial.print(modeName());
  for (int i = 0; i < 6; i++) {
    Serial.print(",");
    Serial.print(lastOutputAngles[i]);
  }
  for (int i = 0; i < 2; i++) {
    Serial.print(",");
    Serial.print(clampAngles[i]);
  }
  Serial.println();
}

void writeClamps(const int a[2]) {
  for (int i = 0; i < 2; i++) {
    clampAngles[i] = constrain(a[i], 0, 180);
    pwm.setPWM(CLAMP_CH[i], 0, angleToPulse(clampAngles[i]));
  }
}

void handleClamp(const String& input) {
  if (isEmergencyStop) {
    Serial.println("ERR:STOPPED");
    return;
  }
  int a[2];
  if (input.equalsIgnoreCase("C,OPEN")) {
    a[0] = CLAMP_OPEN[0]; a[1] = CLAMP_OPEN[1];
  } else if (input.equalsIgnoreCase("C,CLOSE")) {
    a[0] = CLAMP_CLOSE[0]; a[1] = CLAMP_CLOSE[1];
  } else if (!parseInts(input, a, 2)) {
    Serial.print("ERR:BAD_PACKET ");
    Serial.println(input);
    return;
  }
  writeClamps(a);
  Serial.print("STATUS:CLAMP,");
  Serial.print(clampAngles[0]);
  Serial.print(",");
  Serial.println(clampAngles[1]);
}

void reseedFilters() {
  // 播放期間沒有讀可變電阻，回到即時連動前先重設濾波器，避免拿舊值
  for (int i = 0; i < 6; i++) {
    filteredValues[i] = analogRead(potPins[i]);
  }
}

// 解析 "X,a,b,..."：逗號後必須剛好 n 個整數，否則回傳 false
// (舊版用 toInt()，格式壞掉時會變成 0 -> 手臂直衝到 5 度)
bool parseInts(const String& s, int out[], int n) {
  int start = 2;
  for (int i = 0; i < n; i++) {
    int comma = s.indexOf(',', start);
    if (i < n - 1) {
      if (comma == -1) return false;
    } else {
      if (comma != -1) return false;  // 多於 6 個值
      comma = s.length();
    }
    String tok = s.substring(start, comma);
    tok.trim();
    if (tok.length() == 0 || tok.length() > 4) return false;
    for (unsigned int k = 0; k < tok.length(); k++) {
      char c = tok.charAt(k);
      if (!(isDigit(c) || (k == 0 && c == '-'))) return false;
    }
    out[i] = tok.toInt();
    start = comma + 1;
  }
  return true;
}

void handlePlayback(const String& input) {
  if (isEmergencyStop) {
    // 緊急停止中：不動作 (只回報一次，避免 50Hz 洗版)
    if (!stopRejectReported) {
      Serial.println("ERR:STOPPED");
      stopRejectReported = true;
    }
    return;
  }

  int angles[6];
  if (!parseInts(input, angles, 6)) {
    Serial.print("ERR:BAD_PACKET ");
    Serial.println(input);
    return;
  }

  if (!isPlaybackMode) {
    isPlaybackMode = true;
    Serial.println("STATUS:PLAYBACK");
  }

  for (int i = 0; i < 6; i++) {
    // J6 夾爪與即時連動相同可到 J6_OUTPUT_MAX (180)，否則錄製時夾緊、播放時會鬆 5 度
    int a = (i == 5) ? constrain(angles[i], MIN_ANGLE, J6_OUTPUT_MAX)
                     : constrain(angles[i], MIN_ANGLE, MAX_ANGLE);
    if (i < 5) {  // J1~J5 限制單步變化，J6 夾爪需要快速開合不限
      int diff = a - lastOutputAngles[i];
      if (diff > PLAYBACK_MAX_STEP) a = lastOutputAngles[i] + PLAYBACK_MAX_STEP;
      else if (diff < -PLAYBACK_MAX_STEP) a = lastOutputAngles[i] - PLAYBACK_MAX_STEP;
    }
    writeServo(i, a);
  }
}

void handleCommand(String input) {
  input.trim();
  if (input.length() == 0) return;

  if (input.equalsIgnoreCase("s") || input.equalsIgnoreCase("stop")) {
    isEmergencyStop = true;
    stopRejectReported = false;
    Serial.println("STATUS:EMERGENCY_STOP");
  }
  else if (input.equalsIgnoreCase("r") || input.equalsIgnoreCase("run")) {
    isEmergencyStop = false;
    isPlaybackMode = false;
    reseedFilters();
    Serial.println("STATUS:RUNNING");
  }
  else if (input == "?") {
    sendState();
  }
  else if (input.startsWith("P,")) {
    handlePlayback(input);
  }
  else if (input.startsWith("C,") || input.startsWith("c,")) {
    handleClamp(input);
  }
  else {
    Serial.print("ERR:UNKNOWN ");
    Serial.println(input);
  }
}

// 非阻塞讀取：每次 loop 把收到的字元全部處理完，指令不會排隊延遲
void readSerial() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      handleCommand(rxBuffer);
      rxBuffer = "";
    } else if (c != '\r') {
      rxBuffer += c;
      if (rxBuffer.length() > RX_MAX_LEN) {
        rxBuffer = "";
        Serial.println("ERR:LINE_TOO_LONG");
      }
    }
  }
}

// 即時連動：讀取示範臂可變電阻並輸出給 PCA9685
void liveUpdate() {
  int currentAngles[6];

  for (int i = 0; i < 6; i++) {
    int rawVal = analogRead(potPins[i]);
    filteredValues[i] = (alpha * rawVal) + ((1.0 - alpha) * filteredValues[i]);

    int rawAngle = map((int)filteredValues[i], 0, 4095, 0, 180);
    int targetAngle = 90;

    if (i == 5) { // J6 夾爪放大邏輯
      int calibratedRaw = rawAngle + offset[5];
      targetAngle = map(calibratedRaw, J6_INPUT_MIN, J6_INPUT_MAX, J6_OUTPUT_MIN, J6_OUTPUT_MAX);
      targetAngle = constrain(targetAngle, J6_OUTPUT_MIN, J6_OUTPUT_MAX);
    }
    else { // J1~J5
      if (i == 2) { // J3 反向
        rawAngle = 180 - rawAngle;
      }
      targetAngle = rawAngle + offset[i];
      targetAngle = constrain(targetAngle, MIN_ANGLE, MAX_ANGLE);

      int angleDiff = targetAngle - lastOutputAngles[i];
      if (abs(angleDiff) > MAX_SPEED) {
        if (angleDiff > 0) targetAngle = lastOutputAngles[i] + MAX_SPEED;
        else targetAngle = lastOutputAngles[i] - MAX_SPEED;
      }
    }

    writeServo(i, targetAngle);
    currentAngles[i] = targetAngle;
  }

  // 將當前各關節角度回傳給 Python 進行即時錄製或顯示 (格式: DATA,j1,j2,j3,j4,j5,j6)
  Serial.print("DATA,");
  for (int i = 0; i < 6; i++) {
    Serial.print(currentAngles[i]);
    if (i < 5) Serial.print(",");
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  pwm.begin();
  pwm.setPWMFreq(50);
  delay(100);

  writeClamps(CLAMP_OPEN);   // 排夾預設開啟，方便插牌
  reseedFilters();
  rxBuffer.reserve(RX_MAX_LEN + 1);

  Serial.println("READY"); // 傳送就緒訊號給 Python 端
}

void loop() {
  // 1. 處理指令 (任何模式都會處理，緊急停止也能收到 r / ?)
  readSerial();

  // 2. 緊急停止或播放模式：手臂保持在最後的角度，不讀示範臂
  if (isEmergencyStop || isPlaybackMode) return;

  // 3. 即時連動模式：每 20ms 更新一次
  unsigned long now = millis();
  if (now - lastUpdate >= LOOP_INTERVAL_MS) {
    lastUpdate = now;
    liveUpdate();
  }
}
