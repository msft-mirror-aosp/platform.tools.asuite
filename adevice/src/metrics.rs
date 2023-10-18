//! Metrics client

use adevice_proto::clientanalytics::LogEvent;
use adevice_proto::clientanalytics::LogRequest;
use adevice_proto::user_log::adevice_log_event::AdeviceStartEvent;
use adevice_proto::user_log::AdeviceLogEvent;

use anyhow::{anyhow, Result};
use log::debug;
use std::env;
use std::fs;
use std::process::Command;
use std::time::UNIX_EPOCH;

const OUT_ENV: &str = "OUT";
const INTERNAL_USER_GOB_CURL_PATH: &str = "/usr/bin/gob-curl";
const INTERNAL_USER_ENV: &str = "USER";
const CLEARCUT_PROD_URL: &str = "https://play.googleapis.com/log";
const ADEVICE_LOG_SOURCE: i32 = 2265;

pub trait MetricSender {
    fn add_start_event(&mut self, command_line: &str);
}

#[derive(Debug, Clone)]
pub struct Metrics {
    events: Vec<LogEvent>,
    user: String,
    url: String,
}

impl MetricSender for Metrics {
    fn add_start_event(&mut self, command_line: &str) {
        let mut start_event = AdeviceStartEvent::default();
        start_event.set_command_line(command_line.to_string());

        let mut event = self.default_log_event();
        event.set_adevice_start_event(start_event);

        self.events.push(LogEvent {
            event_time_ms: Some(UNIX_EPOCH.elapsed().unwrap().as_millis() as i64),
            source_extension: Some(protobuf::Message::write_to_bytes(&event).unwrap()),
            special_fields: protobuf::SpecialFields::new(),
        });
    }
}

impl Default for Metrics {
    fn default() -> Self {
        Metrics {
            events: Vec::new(),
            user: env::var(INTERNAL_USER_ENV).unwrap_or("".to_string()),
            url: String::from(CLEARCUT_PROD_URL),
        }
    }
}

impl Metrics {
    fn send(&self) -> Result<()> {
        if self.url.is_empty() {
            return Err(anyhow!("Metrics not sent since url is empty"));
        }

        // Only send for internal users, check for gob-curl binary
        if fs::metadata(INTERNAL_USER_GOB_CURL_PATH).is_err() {
            return Err(anyhow!("Not internal user: Metrics not sent since gob-curl not found"));
        }

        // Serialize
        let body = {
            let mut log_request = LogRequest::default();
            log_request.set_log_source(ADEVICE_LOG_SOURCE);

            for e in &*self.events {
                log_request.log_event.push(e.clone());
            }
            let res: Vec<u8> = protobuf::Message::write_to_bytes(&log_request).unwrap();
            res
        };

        // Send to metrics service; sending binary with curl requires making a temp file.

        let out = env::var(OUT_ENV).unwrap_or("/tmp".to_string());
        let temp_dir = format!("{}/adevice", out);
        let temp_file_path = format!("{}/adevice/adevice.bin", out);
        fs::create_dir_all(temp_dir).expect("Failed to create folder for metrics");
        fs::write(temp_file_path.clone(), body).expect("Failed to write to metrics file");
        let output = Command::new("curl")
            .arg("-s")
            .arg("-o")
            .arg("/dev/null")
            .arg("-w")
            .arg("\"%{http_code}\"")
            .arg("-X")
            .arg("POST")
            .arg("--data-binary")
            .arg(format!("@{}", temp_file_path))
            .arg(self.url.clone())
            .output()
            .expect("Failed to send metrics");
        fs::remove_file(temp_file_path)?;

        // TODO implement next_request_wait_millis that comes back in response
        debug!("Metrics upload response: {:?}", output);
        Ok(())
    }

    fn default_log_event(&self) -> AdeviceLogEvent {
        let mut event = AdeviceLogEvent::default();
        event.set_user_key(self.user.to_string());
        event
    }
}

impl Drop for Metrics {
    fn drop(&mut self) {
        match self.send() {
            Ok(_) => debug!("Metrics sent successfully"),
            Err(e) => debug!("Failed to send metrics: {}", e),
        };
    }
}

#[cfg(test)]
#[allow(unused)]
mod tests {
    use super::*;

    #[test]
    fn test_print_events() {
        let mut metrics = Metrics::default();
        metrics.user = "test_user".to_string();
        metrics.url = "".to_string();
        metrics.add_start_event("adevice status");
        metrics.add_start_event("adevice status --verbose debug");

        assert_eq!(metrics.events.len(), 2);
        metrics.send();
        metrics.events.clear();
        assert_eq!(metrics.events.len(), 0);
    }
}
