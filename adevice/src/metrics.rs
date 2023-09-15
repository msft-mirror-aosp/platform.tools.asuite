//! Metrics client

use adevice_proto::clientanalytics::LogEvent;
use adevice_proto::clientanalytics::LogRequest;
use adevice_proto::internal_user_log::atest_log_event_internal::AtestStartEvent;
use adevice_proto::internal_user_log::AtestLogEventInternal;

use anyhow::{anyhow, Result};
use log::debug;
use std::env;
use std::fs;
use std::process::Command;

const OUT_ENV: &str = "OUT";
const INTERNAL_USER_ENV: &str = "USER";
const CLEARCUT_PROD_URL: &str = "https://play.googleapis.com/log";
const ASUITE_LOG_SOURCE: i32 = 971;
const TOOL_NAME: &str = "adevice";

#[derive(Debug, Clone)]
pub struct Metrics {
    events: Vec<AtestLogEventInternal>,
    user: String,
    url: String,
}

impl Metrics {
    pub fn default() -> Self {
        Metrics {
            events: Vec::new(),
            user: env::var(INTERNAL_USER_ENV).unwrap_or("".to_string()),
            url: String::from(CLEARCUT_PROD_URL),
        }
    }

    pub fn add_start_event(&mut self, command_line: &str) {
        let mut start_event = AtestStartEvent::default();
        start_event.set_command_line(command_line.to_string());

        let mut event = self.default_log_event();
        event.set_atest_start_event(start_event);
        self.events.push(event);
    }

    fn send(&self) -> Result<()> {
        if self.url.is_empty() {
            return Err(anyhow!("Metrics not sent since url is empty"));
        }

        // Only send for internal users
        if self.user.is_empty() {
            return Err(anyhow!("Metrics not sent since USER env is not set"));
        }

        // Serialize
        let body = {
            let mut log_request = LogRequest::default();
            log_request.set_log_source(ASUITE_LOG_SOURCE);

            for e in &*self.events {
                log_request.log_event.push(LogEvent {
                    event_time_ms: ::std::option::Option::None,
                    source_extension: Some(protobuf::Message::write_to_bytes(e).unwrap()),
                    special_fields: protobuf::SpecialFields::new(),
                });
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
        fs::remove_file(temp_file_path).expect("Failed to remove metrics file");

        // TODO implement next_request_wait_millis that comes back in response
        debug!("Metrics upload response: {:?}", output);
        Ok(())
    }

    fn default_log_event(&self) -> AtestLogEventInternal {
        let mut event = AtestLogEventInternal::default();
        event.set_user_key(self.user.to_string());
        event.set_tool_name(TOOL_NAME.to_string());
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
