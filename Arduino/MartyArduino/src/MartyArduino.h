#pragma once

#include "MiniHDLC.h"
#include <HardwareSerial.h>
#include <Stream.h>
#include <string.h>

class Marty {
public:
  //Marty(SoftwareSerial &s) : _serial(s){_hwSerial = false;}
  Marty(HardwareSerial &s) : _serial(s){_hwSerial = true;}

  MiniHDLC _hdlc = MiniHDLC(std::bind(&Marty::_frameTx, this, std::placeholders::_1, std::placeholders::_2), std::bind(&Marty::_frameRx, this, std::placeholders::_1, std::placeholders::_2), 0xE7, 0xD7);
  Stream &_serial;
  bool _hwSerial;

  void init(){
    if (_hwSerial) static_cast<HardwareSerial&>(_serial).begin(921600);
  }

  void sendCommand(String cmdStr);

  void _frameRx(const uint8_t *framebuffer, unsigned framelength){
  }

  void _frameTx(const uint8_t *framebuffer, unsigned framelength){
    _serial.write(framebuffer, framelength);
  }

  void standStraight(){
    sendCommand("traj/standStraight");
  }

  void dance(uint16_t move_time=3000, bool blocking=true);
  void wiggle(uint16_t move_time=4000, bool blocking=true);
  void sidestep(String side="left", uint8_t steps=1, uint8_t step_length=35, uint16_t move_time=1000, bool blocking=true);
  void arms(int8_t left_angle=0, int8_t right_angle=0, uint16_t move_time=1000, bool blocking=true);
  void walk(uint8_t steps=1, int8_t turn=0, int8_t step_length=25, uint16_t move_time=1500, bool blocking=true);

};