#include "MartyArduino.h"

void Marty::sendCommand(String cmdStr){
  uint8_t cmdFrame[255]{0};
  uint8_t encodedFrame[255]{0};
  uint8_t msgNum = 2;
  uint8_t MSG_TYPE_COMMAND = 0x00;
  uint8_t PROTOCOL_RICREST = 0x02;
  uint8_t RICREST_ELEM_CODE_URL = 0x00;
  uint8_t frameLen = cmdStr.length() + 3;
  // TODO: why does it not work if we add the message number?
  //cmdFrame[0] = msgNum;
  cmdFrame[0] = MSG_TYPE_COMMAND + PROTOCOL_RICREST;
  cmdFrame[1] = RICREST_ELEM_CODE_URL;
  strcpy((char*)&cmdFrame[2], cmdStr.c_str());
  
  uint32_t encodedLen = _hdlc.encodeFrame(encodedFrame, sizeof(encodedFrame), cmdFrame, frameLen);
  _hdlc.sendFrame(encodedFrame, encodedLen);
}

void Marty::dance(uint16_t move_time, bool blocking){
  String cmd = "traj/dance?moveTime=";
  cmd += move_time;
  sendCommand(cmd);
  if (blocking) delay(move_time);
}

void Marty::wiggle(uint16_t move_time, bool blocking){
  String cmd = "traj/wiggle?moveTime=";
  cmd += move_time;
  sendCommand(cmd);
  if (blocking) delay(move_time);
}

void Marty::sidestep(String side, uint8_t steps, uint8_t step_length, uint16_t move_time, bool blocking){
  uint8_t sideCode = 0;
  if (side == "right") sideCode = 1;
  String cmd = "traj/sidestep?side=" + sideCode;
  cmd += "&stepLength=" + step_length;
  cmd += "&moveTime=" + move_time;
  for (uint8_t i=0; i<steps; i++){
    sendCommand(cmd);
    if (blocking) delay(move_time);
  }
}

void Marty::arms(int8_t left_angle, int8_t right_angle, uint16_t move_time, bool blocking){
  String cmd = "traj/joint?jointID=6&angle=";
  cmd += left_angle;
  cmd += "&moveTime=" + move_time;
  sendCommand(cmd);
  cmd = "traj/joint?jointID=7&angle=";
  cmd += right_angle;
  cmd += "&moveTime=" + move_time;
  sendCommand(cmd);
  if (blocking) delay(move_time);
}

void Marty::walk(uint8_t steps, int8_t turn, int8_t step_length, uint16_t move_time, bool blocking){
  String cmd = "traj/step?stepLength=";
  cmd += step_length;
  cmd += "&moveTime=" + move_time;
  for (uint8_t i=0; i<steps; i++){  
    sendCommand(cmd);
    if (blocking) delay(move_time);
  }
}