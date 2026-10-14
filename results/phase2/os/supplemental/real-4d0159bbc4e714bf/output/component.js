// fixture-component Component
// Basic A-Frame component with schema and lifecycle methods

AFRAME.registerComponent('fixture-component', {
  // Component schema (configuration properties)
  schema: {
    enabled: { type: 'boolean', default: true },
    speed: { type: 'number', default: 1 },
    color: { type: 'color', default: '#FFF' }
  },

  // Initialize (called once when component is attached)
  init: function() {
    console.log('fixture-component initialized');

    // Store references
    this.el; // The entity element
    this.data; // Component data from schema
    this.el.sceneEl; // The scene element

    // Setup code here
  },

  // Update (called when component properties change)
  update: function(oldData) {
    // this.data contains new values
    // oldData contains previous values

    if (this.data.enabled !== oldData.enabled) {
      console.log('Enabled changed to:', this.data.enabled);
    }

    if (this.data.speed !== oldData.speed) {
      console.log('Speed changed to:', this.data.speed);
    }
  },

  // Remove (called when component is removed from entity)
  remove: function() {
    // Cleanup code here
    console.log('fixture-component removed');
  },

  // Pause (called when entity/scene pauses)
  pause: function() {
    console.log('fixture-component paused');
  },

  // Play (called when entity/scene plays)
  play: function() {
    console.log('fixture-component playing');
  }
});

// Usage:
// <a-entity fixture-component="enabled: true; speed: 2; color: #FF0000"></a-entity>
