#include <Servo.h>

const int servopin = 4; 

const int m11 = 11;  
const int m12 = 10;  
const int m21 = 8; 
const int m22 = 9; 

Servo myservopin;

void setup() {
  myservopin.attach(servopin);
  myservopin.write(0);
  
  pinMode(m11, OUTPUT);
  pinMode(m12, OUTPUT);
  pinMode(m21, OUTPUT);
  pinMode(m22, OUTPUT);
}

void loop() {
  digitalWrite(m11, HIGH);
  digitalWrite(m12, LOW);
  digitalWrite(m21, HIGH);
  digitalWrite(m22, LOW);
  
  delay(3000);                    
  
  digitalWrite(m11, LOW);
  digitalWrite(m12, LOW);
  digitalWrite(m21, LOW);
  digitalWrite(m22, LOW);
  
  delay(1000);                     

  for (int pos = 0; pos <= 120; pos += 1) {
    myservopin.write(pos);
    delay(20);                 
  }
  
  delay(1500);                      
  
  for (int pos = 120; pos >= 0; pos -= 1) {
    myservopin.write(pos);
    delay(20);                     
  }
  delay(1000);
  digitalWrite(m11, HIGH);
  digitalWrite(m12, LOW);
  digitalWrite(m21, LOW);
  digitalWrite(m22, HIGH);
  delay(1500);
  digitalWrite(m11, LOW);
  digitalWrite(m12, LOW);
  digitalWrite(m21, LOW);
  digitalWrite(m22, LOW);
  delay(1000);                       
}
